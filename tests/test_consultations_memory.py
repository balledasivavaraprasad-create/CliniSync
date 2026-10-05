import pytest
import json
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import get_db_context
from app.models.patient import Patient
from app.models.clinical_fact import ClinicalFact
from app.models.consultation import Consultation
from app.models.clinical_memory import ClinicalMemory
from app.models.timeline_event import TimelineEvent
from app.utils.ids import patient_id, fact_id
from app.services.consultation_service import consultation_service

client = TestClient(app)

@pytest.mark.anyio
async def test_consultation_lifecycle_and_gate1_approval():
    with get_db_context() as db:
        pid = patient_id()
        p = Patient(id=pid, full_name="Memory Test Patient", age_years=48)
        db.add(p)
        db.flush()

        f1 = ClinicalFact(
            id=fact_id(),
            patient_id=pid,
            fact_type="diagnosis",
            value="Essential Hypertension",
            source_text="Essential Hypertension",
            provenance_verified=True,
            confidence=0.95
        )
        db.add(f1)
        db.commit()

    # 1. Create Consultation Draft
    res_draft = client.post(f"/api/v1/patients/{pid}/consultations", json={"specialty": "cardiology"})
    assert res_draft.status_code == 201
    draft_data = res_draft.json()["data"]
    cid = draft_data["id"]
    assert draft_data["status"] == "draft"
    assert draft_data["version"]["origin"] == "ai_generated"

    # Invariant check: examination, assessment, and plan must be empty in AI draft
    ai_content = draft_data["version"]["content"]
    assert ai_content["examination"] == ""
    assert ai_content["assessment"] == ""
    assert ai_content["plan"] == ""

    # 2. Doctor Edits and Adds Assessment & Plan (Version 2)
    doctor_content = dict(ai_content)
    doctor_content["examination"] = "BP: 138/86 mmHg, HR: 74 bpm. Normal S1/S2."
    doctor_content["assessment"] = "Mild Essential Hypertension, stable."
    doctor_content["plan"] = "Continue lifestyle modifications and monitor blood pressure weekly."

    res_v2 = client.post(
        f"/api/v1/consultations/{cid}/versions",
        json={"content": doctor_content, "change_summary": "Doctor added physical exam, assessment, and plan."}
    )
    assert res_v2.status_code == 200
    v2_data = res_v2.json()["data"]
    assert v2_data["version_number"] == 2
    assert v2_data["origin"] == "doctor_edited"

    # 3. Dry-Run Preview Approval
    res_preview = client.post(
        f"/api/v1/consultations/{cid}/approve/preview",
        json={"acknowledged_unedited": False}
    )
    assert res_preview.status_code == 200
    preview_data = res_preview.json()["data"]
    print("\nPREVIEW CHECKS:", preview_data["checks"])

    # Gate 1 fails **closed** by design when the faithfulness judge cannot run
    # (§12.1): nothing AI-derived may reach clinical memory unjudged. That is
    # correct behaviour, but it makes this assertion depend on a live
    # third-party model, so a provider rate-limit shows up as a failure even
    # though the code is fine. Skip with a reason rather than reporting a false
    # regression — a genuine judge *block* still fails, because that is not
    # `judge_unavailable`.
    if preview_data["can_approve"] is not True:
        unavailable = any(
            "judge service is unavailable" in str(c.get("detail", ""))
            for c in preview_data["checks"]
            if not c.get("passed")
        )
        if unavailable:
            pytest.skip(
                "Gate 1 failed closed: the external validation judge is "
                "unavailable (provider rate-limit / no network). Re-run when a "
                "judge provider is reachable."
            )
    assert preview_data["can_approve"] is True
    assert len(preview_data["proposed_memory_items"]) >= 1

    # 4. Gate 1 Approval Commit
    #
    # `approve` re-runs Gate 1 rather than trusting the preview, which is correct
    # (the content may have changed) but means a second call to the external
    # judge. If the judge rate-limits on that second call the API answers 503
    # `VALIDATION_UNAVAILABLE` — an outage, not a rejection — so skip with a
    # reason instead of reporting a false regression. A real content block is
    # 422 `GATE1_BLOCKED` and still fails, as it should.
    res_approve = client.post(
        f"/api/v1/consultations/{cid}/approve",
        json={"acknowledged_unedited": False}
    )
    if res_approve.status_code == 503:
        pytest.skip(
            "Gate 1 failed closed on approve: the external validation judge "
            "became unavailable (provider rate-limit / no network)."
        )
    assert res_approve.status_code == 200
    appr_data = res_approve.json()["data"]
    assert appr_data["status"] == "approved"
    assert appr_data["memory_items_created"] >= 2

    # 5. Verify Clinical Memory Persistence (INV-1)
    with get_db_context() as db:
        memories = db.query(ClinicalMemory).filter(ClinicalMemory.patient_id == pid).all()
        assert len(memories) >= 2
        mem_types = [m.memory_type for m in memories]
        assert "assessment" in mem_types
        assert "plan_note" in mem_types
        for m in memories:
            assert m.verified is True
            assert m.source_consultation_id == cid

        # Verify Timeline approved_note
        tl_notes = db.query(TimelineEvent).filter(
            TimelineEvent.patient_id == pid,
            TimelineEvent.event_type == "approved_note"
        ).all()
        assert len(tl_notes) >= 1

        # Verify Consultation is locked to approved
        cns = db.query(Consultation).filter(Consultation.id == cid).first()
        assert cns.status == "approved"
        assert cns.approved_at is not None

    # 6. Verify Memory Retrieval Endpoints
    res_mem = client.get(f"/api/v1/patients/{pid}/memory")
    assert res_mem.status_code == 200
    mem_list = res_mem.json()["data"]
    assert len(mem_list) >= 2
    assert all(m["verified"] is True for m in mem_list)

    print("\n✓ Phase 8 Consultations, Gate 1 Approval & Verified Clinical Memory verified successfully!")
