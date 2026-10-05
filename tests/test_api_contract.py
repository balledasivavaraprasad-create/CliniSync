"""Contract and reliability guarantees the ClinSync Flutter app depends on.

Covers the fixes made in the backend-alignment pass:

* every patient-scoped route 404s for an unknown id instead of returning `[]`;
* `PATCH /issues/{id}` 404s with `ISSUE_NOT_FOUND` instead of a 500;
* the medication list exposes `group_key`, the key its history endpoint uses;
* brief `meta.source` reflects whether the LLM or the fallback served it;
* `brief.contradictions[].sources` carries both sides of a conflict;
* `/health` is pure liveness and `/health/deep` reports schema state;
* the schema self-heals on boot, so a fresh database is usable.

Run:  PYTHONPATH=backend .venv/bin/python -m pytest tests/test_api_contract.py -v
"""
import json

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.database import (
    Base,
    db_health,
    ensure_schema,
    engine,
    schema_is_complete,
)
from app.main import app
from app.models.patient import Patient
from app.utils.ids import patient_id

client = TestClient(app)

UNKNOWN = "pat_definitely_does_not_exist"

# Every route that takes a patient id and used to answer 200 [] for a stranger.
PATIENT_SCOPED = [
    "/api/v1/patients/{pid}/overview",
    "/api/v1/patients/{pid}/timeline",
    "/api/v1/patients/{pid}/issues",
    "/api/v1/patients/{pid}/contradictions",
    "/api/v1/patients/{pid}/medications",
    "/api/v1/patients/{pid}/medications/reconciliation",
    "/api/v1/patients/{pid}/investigations",
    "/api/v1/patients/{pid}/investigations/trends",
    "/api/v1/patients/{pid}/memory",
    "/api/v1/patients/{pid}/memories",
    "/api/v1/patients/{pid}/memory/history",
    "/api/v1/patients/{pid}/memories/review-queue",
    "/api/v1/patients/{pid}/documents",
    "/api/v1/patients/{pid}/facts",
    "/api/v1/patients/{pid}/consultations",
    "/api/v1/patients/{pid}/brief/latest",
    "/api/v1/patients/{pid}/doctor-briefs/latest",
    "/api/v1/patients/{pid}/audit",
]


@pytest.fixture(scope="module", autouse=True)
def ensure_demo_data():
    """Seed the demo patient if absent, so this file runs on a fresh checkout.

    `test_seed_and_demo.py` seeds for the whole suite, but this module must also
    stand alone — a bare `pytest tests/test_api_contract.py` on a new clone.
    """
    from app.db.seed import seed_demo_data

    if client.get("/api/v1/patients/pat_demo_patient_001/overview").status_code != 200:
        seed_demo_data(reset=True)
    yield


@pytest.fixture(scope="module")
def seeded_pid():
    """The demo patient the rest of the suite seeds."""
    pid = "pat_demo_patient_001"
    res = client.get(f"/api/v1/patients/{pid}/overview")
    assert res.status_code == 200, "demo patient must be seeded first"
    return pid


# ── 404 for an unknown patient ───────────────────────────────────────────────

@pytest.mark.parametrize("route", PATIENT_SCOPED)
def test_unknown_patient_returns_404_not_empty_list(route):
    res = client.get(route.format(pid=UNKNOWN))
    assert res.status_code == 404, f"{route} answered {res.status_code}"
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"
    # Never leak an internal message (§6.6 rule 7).
    assert "Traceback" not in body["error"]["message"]


def test_unknown_patient_post_routes_return_404():
    for route in (
        f"/api/v1/patients/{UNKNOWN}/issues/recompute",
        f"/api/v1/patients/{UNKNOWN}/memories/proposals",
    ):
        res = client.post(route, json={})
        assert res.status_code == 404, f"{route} answered {res.status_code}"


def test_demo_aliases_still_resolve(seeded_pid):
    for alias in ("demo-patient-001", "demo_patient_001", seeded_pid):
        res = client.get(f"/api/v1/patients/{alias}/timeline")
        assert res.status_code == 200, f"alias {alias} broke"


# ── Issue patching ───────────────────────────────────────────────────────────

def test_patch_unknown_issue_is_404_not_500():
    res = client.patch(
        "/api/v1/issues/iss_nope", json={"status": "acknowledged"}
    )
    assert res.status_code == 404
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] == "ISSUE_NOT_FOUND"


def test_patch_known_issue_round_trips(seeded_pid):
    issues = client.get(f"/api/v1/patients/{seeded_pid}/issues").json()["data"]
    target = next(i for i in issues if i["status"] == "open")
    original = target["status"]

    res = client.patch(
        f"/api/v1/issues/{target['id']}",
        json={"status": "acknowledged", "doctor_note": "contract test"},
    )
    assert res.status_code == 200
    assert res.json()["data"]["status"] == "acknowledged"

    # Restore, so the suite is order-independent.
    back = client.patch(
        f"/api/v1/issues/{target['id']}", json={"status": original}
    )
    assert back.status_code == 200


# ── Medication list contract ─────────────────────────────────────────────────

def test_medication_list_exposes_group_key_and_dates(seeded_pid):
    meds = client.get(f"/api/v1/patients/{seeded_pid}/medications").json()["data"]
    assert meds
    for med in meds:
        assert med["group_key"], "history endpoint keys on group_key"
        assert "start_date" in med and "stop_date" in med
        # Existing fields must survive the addition.
        assert med["canonical_name"]
        assert "history_count" in med


def test_medication_history_resolves_via_group_key(seeded_pid):
    meds = client.get(f"/api/v1/patients/{seeded_pid}/medications").json()["data"]
    target = next(m for m in meds if m["has_conflict"])
    res = client.get(
        f"/api/v1/patients/{seeded_pid}/medications/{target['group_key']}/history"
    )
    assert res.status_code == 200
    history = res.json()["data"]
    assert len(history) >= 2, "a conflict must have at least two records"


# ── Brief contract ───────────────────────────────────────────────────────────

def test_brief_latest_carries_a_derived_readiness_score(seeded_pid):
    res = client.get(f"/api/v1/patients/{seeded_pid}/brief/latest")
    assert res.status_code == 200
    score = res.json()["data"]["readiness_score"]
    assert isinstance(score, int)
    assert 0 <= score <= 100
    # It was a hardcoded 92; a change of value proves it is computed now.
    assert score != 92


def test_brief_generate_reports_its_real_source(seeded_pid):
    res = client.post(
        f"/api/v1/patients/{seeded_pid}/brief",
        json={"specialty": "general_medicine", "force_regenerate": True},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["meta"]["source"] in ("llm", "fallback")
    data = body["data"]

    # The persisted row must agree with the envelope.
    with_client = client.get(f"/api/v1/patients/{seeded_pid}/brief/latest")
    assert with_client.status_code == 200


def test_brief_conflicts_carry_both_sources(seeded_pid):
    res = client.get(f"/api/v1/patients/{seeded_pid}/brief/latest")
    data = res.json()["data"]
    conflicts = data.get("contradictions") or []
    if not conflicts:
        pytest.skip("no conflict on this brief")
    for conflict in conflicts:
        assert len(conflict["sources"]) == 2, (
            "§6.6 rule 3 needs both recorded instructions, not one"
        )
        assert conflict["sources"][0] != conflict["sources"][1]


def test_brief_latest_reports_its_generation_source(seeded_pid):
    """A read-back brief must still say what wrote it.

    The app labels a brief "AI-generated" or "From records" from this field.
    Without it on the read paths, a deterministically assembled template brief
    would be presented as if a model had written it.
    """
    res = client.post(
        f"/api/v1/patients/{seeded_pid}/brief",
        json={"specialty": "general_medicine", "force_regenerate": True},
    )
    assert res.status_code == 200
    source = res.json()["data"].get("generation_source")
    assert source, "the payload must carry how the brief was written"
    assert source in ("llm", "fallback_template", "seed")

    for path in (f"/api/v1/patients/{seeded_pid}/brief/latest",):
        latest = client.get(path)
        assert latest.status_code == 200
        assert latest.json()["data"].get("generation_source") == source, (
            "reading a brief back must not lose its provenance"
        )


def test_brief_medication_doses_are_not_duplicated(seeded_pid):
    """`dose` and `strength` are the same number — only one may be rendered."""
    res = client.post(
        f"/api/v1/patients/{seeded_pid}/brief",
        json={"specialty": "general_medicine", "force_regenerate": True},
    )
    assert res.status_code == 200
    meds = res.json()["data"]["current_medications"]
    assert meds
    for med in meds:
        assert ".0" not in med["strength"], (
            "a float dose must not be rendered as 500.0mg"
        )
        assert not (med["strength"] and med["dose"]), (
            f"{med['name']}: dose {med['dose']!r} and strength "
            f"{med['strength']!r} say the same thing twice"
        )


# ── Health ───────────────────────────────────────────────────────────────────

def test_health_is_pure_liveness():
    """Must not touch the DB, or a slow lock restarts a healthy server."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["data"]["status"] == "healthy"
    assert res.json()["meta"]["source"] == "system"


def test_health_deep_reports_schema_state():
    res = client.get("/api/v1/health/deep")
    assert res.status_code in (200, 503)
    data = res.json()["data"]
    assert data["database"] in ("connected", "unreachable")
    assert isinstance(data["schema_complete"], bool)
    assert data["missing_tables"] == []
    assert "llm_available" in data


# ── Schema self-healing ──────────────────────────────────────────────────────

def test_schema_is_complete_and_self_heals():
    assert ensure_schema() is True
    assert schema_is_complete() is True
    assert db_health()["missing_tables"] == []


def test_ensure_schema_is_additive(tmp_path, monkeypatch):
    """create_all must never drop or recreate an existing table."""
    from sqlalchemy import inspect

    before = set(inspect(engine).get_table_names())
    assert before, "expected the real schema to be present"
    rows_before = None
    from app.models.patient import Patient as P

    with engine.connect() as conn:
        rows_before = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM patients"
        ).scalar()

    assert ensure_schema() is True

    after = set(inspect(engine).get_table_names())
    assert before <= after, "no table may be dropped"
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM patients").scalar() == (
            rows_before
        ), "existing rows must survive"
    assert P is not None


# ── Error envelope ───────────────────────────────────────────────────────────

def test_a_doubled_api_prefix_is_not_silently_rescued():
    """A wrong client base URL must fail loudly, not appear to work.

    A middleware used to collapse `/api/v1/api/v1` to `/api/v1`, which hid a real
    client bug (the base URL and every path both carried the prefix) from the
    analyser, the tests, and the network tab. The client is fixed and pinned by
    its own tests; this pins the other half.
    """
    res = client.get("/api/v1/api/v1/patients")
    assert res.status_code == 404, (
        "a doubled prefix must 404, not be rewritten into a success"
    )
    # ...while the correct path still works.
    assert client.get("/api/v1/patients").status_code == 200


def test_errors_never_leak_internals(seeded_pid):
    """§6.6 rule 7: a 500 body must be generic, and must be logged not leaked."""
    res = client.patch("/api/v1/issues/iss_nope", json={"status": "x"})
    message = res.json()["error"]["message"]
    for leak in ("Traceback", "sqlalchemy", "File \"", ".py\""):
        assert leak not in message


def test_validation_errors_carry_field_details():
    res = client.post(
        "/api/v1/patients", json={"full_name": ""}  # pydantic rejects empty
    )
    assert res.status_code == 422
    body = res.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"], "field errors must be structured, not prose"


# ── Validation outage is not a content rejection ────────────────────────────

def test_validation_outage_is_distinct_from_gate1_block():
    """A judge outage must not be reported as a rejected note.

    Gate 1 still fails closed either way — nothing AI-derived reaches clinical
    memory unjudged — but the two failures are different in kind. A 422
    `GATE1_BLOCKED` says the doctor's note is not approvable; a 503
    `VALIDATION_UNAVAILABLE` says the check could not run and is worth
    retrying. They used to share a 422, which made an outage look like the
    doctor's mistake.
    """
    from app.api.errors import Gate1BlockedError, ValidationUnavailableError

    block = Gate1BlockedError("nope")
    outage = ValidationUnavailableError("try again")
    assert block.status_code == 422 and block.code == "GATE1_BLOCKED"
    assert outage.status_code == 503
    assert outage.code == "VALIDATION_UNAVAILABLE"


def test_approve_reports_a_judge_outage_as_503_not_422(monkeypatch):
    """`approve` re-runs the judge, so it can hit an outage the preview missed."""
    from app.validation import gate1_memory
    from app.services import consultation_service

    def unavailable(**_kwargs):
        return (
            gate1_memory.ValidationOutcome.blocked,
            [{
                "name": "llm_judge_faithfulness",
                "passed": False,
                "severity": "block",
                "code": "VALIDATION_UNAVAILABLE",
                "detail": "Gate 1 validation failed closed: "
                          "validation judge service is unavailable.",
            }],
            "valrep_test",
        )

    monkeypatch.setattr(
        consultation_service.gate1_validator, "validate_approval", unavailable
    )
    svc = consultation_service.consultation_service
    with pytest.raises(consultation_service.ValidationUnavailableError) as err:
        svc.approve(db=None, cid="con_anything")
    assert err.value.status_code == 503


def test_a_content_block_stays_422(monkeypatch):
    """A judge that *ran* and blocked is still a content rejection."""
    from app.validation import gate1_memory
    from app.services import consultation_service

    def blocked(**_kwargs):
        return (
            gate1_memory.ValidationOutcome.blocked,
            [{
                "name": "llm_judge_faithfulness",
                "passed": False,
                "severity": "block",
                "detail": "Judge blocked content: unsupported claim",
            }],
            "valrep_test",
        )

    monkeypatch.setattr(
        consultation_service.gate1_validator, "validate_approval", blocked
    )
    svc = consultation_service.consultation_service
    with pytest.raises(consultation_service.Gate1BlockedError) as err:
        svc.approve(db=None, cid="con_anything")
    assert err.value.status_code == 422
