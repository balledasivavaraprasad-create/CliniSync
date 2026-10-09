from pathlib import Path
import time
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.seed import seed_demo_data, DEMO_PATIENT_ID

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def run_seed():
    seed_demo_data(reset=True)


def test_seed_patient():
    resp = client.get(f"/api/v1/patients/{DEMO_PATIENT_ID}")
    assert resp.status_code == 200
    res = resp.json()
    assert res["success"] is True
    pt = res["data"]
    assert pt["id"] == DEMO_PATIENT_ID
    assert pt["full_name"] == "Demo Patient"
    assert pt["sex"] == "male"
    assert pt["is_demo"] is True


def test_seed_documents_and_files():
    resp = client.get(f"/api/v1/patients/{DEMO_PATIENT_ID}/documents")
    assert resp.status_code == 200
    res = resp.json()
    assert res["success"] is True
    docs = res["data"]
    assert len(docs) == 6

    # Verify physical file existence in storage
    for d in docs:
        file_resp = client.get(f"/api/v1/documents/{d['id']}/file")
        assert file_resp.status_code == 200
        assert len(file_resp.content) > 0


def test_seed_timeline():
    resp = client.get(f"/api/v1/patients/{DEMO_PATIENT_ID}/timeline")
    assert resp.status_code == 200
    res = resp.json()
    assert res["success"] is True
    events = res["data"]
    assert len(events) >= 6

    # Verify dates are chronologically ordered (descending, latest first)
    dates = [e["event_date"] for e in events if e.get("event_date")]
    assert dates == sorted(dates, reverse=True)


def test_seed_medications_and_conflict():
    resp = client.get(f"/api/v1/patients/{DEMO_PATIENT_ID}/medications")
    assert resp.status_code == 200
    res = resp.json()
    assert res["success"] is True
    meds = res["data"]
    assert any(m["canonical_name"] == "metformin" for m in meds)
    assert any(m["canonical_name"] == "glimepiride" for m in meds)

    # Check issues for medication conflict
    issues_resp = client.get(f"/api/v1/patients/{DEMO_PATIENT_ID}/issues?type=medication_conflict")
    assert issues_resp.status_code == 200
    issues = issues_resp.json()["data"]
    assert len(issues) >= 1
    assert any("metformin" in i["title"].lower() or "metformin" in i["description"].lower() for i in issues)


def test_seed_repeated_investigations_and_trends():
    resp = client.get(f"/api/v1/patients/{DEMO_PATIENT_ID}/investigations")
    assert resp.status_code == 200
    res = resp.json()
    assert res["success"] is True
    invs = res["data"]
    # GET /investigations returns latest value per unique test (Section 8.2)
    assert len(invs) >= 3


    # Trend verification for hba1c
    trend_resp = client.get(f"/api/v1/patients/{DEMO_PATIENT_ID}/investigations/hba1c/trend")
    assert trend_resp.status_code == 200
    trend = trend_resp.json()["data"]
    assert trend["test"] == "hba1c"
    assert len(trend["series"]) == 3
    # Verify sequential values: 8.4 -> 8.0 -> 7.8
    values = [p["value"] for p in trend["series"]]
    assert values == [8.4, 8.0, 7.8]
    assert trend["direction"] == "down"
    # Verify non-causal description per INV-6
    assert "because of" not in trend["description"]
    assert "due to" not in trend["description"]



def test_seed_missing_information():
    resp = client.get(f"/api/v1/patients/{DEMO_PATIENT_ID}/issues?type=missing_information")
    assert resp.status_code == 200
    res = resp.json()
    assert res["success"] is True
    issues = res["data"]
    assert len(issues) >= 1
    # Check that prompts exist without guessed values per INV-5
    titles = [i["title"].lower() for i in issues]
    assert any("allergy" in t or "missing" in t for t in titles)


def test_seed_doctor_brief():
    resp = client.get(f"/api/v1/patients/{DEMO_PATIENT_ID}/brief/latest")
    assert resp.status_code == 200
    res = resp.json()
    assert res["success"] is True
    brief = res["data"]
    assert brief["patient"]["id"] == DEMO_PATIENT_ID
    assert len(brief["important_trends"]) >= 1
    assert len(brief["current_medications"]) >= 2
    assert "disclaimer" in brief


def test_seed_consultations_and_memory():
    resp = client.get(f"/api/v1/patients/{DEMO_PATIENT_ID}/consultations")
    assert resp.status_code == 200
    consultations = resp.json()["data"]
    assert len(consultations) >= 1
    con = consultations[0]
    assert con["status"] == "approved"

    # Versions
    ver_resp = client.get(f"/api/v1/consultations/{con['id']}/versions")
    assert ver_resp.status_code == 200
    versions = ver_resp.json()["data"]
    assert len(versions) == 3
    origins = [v["origin"] for v in versions]
    assert "ai_generated" in origins
    assert "doctor_edited" in origins
    assert "approved" in origins

    # Clinical memory
    mem_resp = client.get(f"/api/v1/patients/{DEMO_PATIENT_ID}/memory")
    assert mem_resp.status_code == 200
    memories = mem_resp.json()["data"]
    assert len(memories) >= 2
    assert all(m["verified"] is True for m in memories)


def test_overview_performance_target():
    """Verify overview endpoint completes in < 300 ms per Section 20"""
    t0 = time.perf_counter()
    resp = client.get(f"/api/v1/patients/{DEMO_PATIENT_ID}/overview")
    t1 = time.perf_counter()
    latency_ms = (t1 - t0) * 1000

    assert resp.status_code == 200
    res = resp.json()
    assert res["success"] is True
    data = res["data"]

    # Verify all 8 components
    assert "patient" in data
    assert "source_count" in data and data["source_count"] == 6
    assert "latest_brief" in data and data["latest_brief"] is not None
    assert "attention_items" in data
    assert "timeline_preview" in data
    assert "current_medications" in data
    assert "latest_investigations" in data
    assert "memory_summary" in data
    assert "open_issue_counts" in data

    print(f"\n✓ Overview endpoint response time: {latency_ms:.1f}ms (Target: < 300ms)")
    assert latency_ms < 300


def test_specialties_and_audit():
    spec_resp = client.get("/api/v1/specialties")
    assert spec_resp.status_code == 200
    specialties = spec_resp.json()["data"]
    assert len(specialties) >= 6

    audit_resp = client.get(f"/api/v1/patients/{DEMO_PATIENT_ID}/audit")
    assert audit_resp.status_code == 200
    assert audit_resp.json()["success"] is True


def test_seed_idempotency():
    # Re-running seed should cleanly reset without duplicating records
    seed_demo_data(reset=True)

    pts_resp = client.get(f"/api/v1/patients/{DEMO_PATIENT_ID}")
    assert pts_resp.status_code == 200

    docs_resp = client.get(f"/api/v1/patients/{DEMO_PATIENT_ID}/documents")
    assert docs_resp.status_code == 200
    assert len(docs_resp.json()["data"]) == 6
