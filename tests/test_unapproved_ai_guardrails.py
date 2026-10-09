"""Dedicated regression test suite for unapproved AI guardrails and clinical workflow state transitions.

Verifies:
1. State transition enforcement:
   AI_GENERATED -> REVIEW_REQUIRED -> DOCTOR_EDITED -> VALIDATION -> APPROVED -> MEMORY_UPDATE
2. Invalid transitions rejected:
   - AI_GENERATED -> MEMORY directly rejected.
   - UNVERIFIED -> APPROVED rejected unless resolved by doctor workflow.
   - CONFLICTING -> CURRENT rejected until resolved.
3. Only authorized doctor/admin can approve clinical information.
4. Storage of doctor ID, consultation ID, version ID, approval timestamp, and content hash upon approval.
5. Preservation of original AI-generated version (v1) even after doctor edits.
"""
import pytest
import json
import hashlib
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_db_context
from app.models.patient import Patient
from app.models.user import User
from app.models.patient_access import PatientAccess
from app.models.clinical_fact import ClinicalFact
from app.models.clinical_memory import ClinicalMemory
from app.models.consultation import Consultation, ConsultationVersion
from app.models.timeline_event import TimelineEvent
from app.utils.ids import patient_id, fact_id, consultation_id, version_id, clinical_memory_id, user_id
from app.utils.tokens import create_access_token
from app.schemas.common import ConsultationOrigin
from app.api.errors import Gate1BlockedError, InvalidStateTransitionError

client = TestClient(app)


@pytest.fixture
def test_setup():
    with get_db_context() as db:
        pid = patient_id()
        doc_id = user_id()
        nurse_id = user_id()

        pat = Patient(id=pid, full_name="Guardrail Safety Test Patient", age_years=52)
        db.add(pat)

        doc_user = User(
            id=doc_id,
            email=f"dr.guardrail.{doc_id}@clinsync.health",
            hashed_password="testhash",
            full_name="Dr. Guardrail MD",
            role="doctor",
            specialty="Cardiology",
            is_active=True,
        )
        db.add(doc_user)

        nurse_user = User(
            id=nurse_id,
            email=f"nurse.guardrail.{nurse_id}@clinsync.health",
            hashed_password="testhash",
            full_name="Nurse Guardrail RN",
            role="nurse",
            specialty="Nursing",
            is_active=True,
        )
        db.add(nurse_user)

        db.flush()

        access_doc = PatientAccess(
            id=f"acc_{doc_id}_{pid}",
            user_id=doc_id,
            patient_id=pid,
            access_level="read_write",
        )
        access_nurse = PatientAccess(
            id=f"acc_{nurse_id}_{pid}",
            user_id=nurse_id,
            patient_id=pid,
            access_level="read_write",
        )
        db.add_all([access_doc, access_nurse])
        db.commit()

        doc_token = create_access_token(subject=doc_id, claims={"email": doc_user.email, "role": "doctor"})
        nurse_token = create_access_token(subject=nurse_id, claims={"email": nurse_user.email, "role": "nurse"})

        return {
            "patient_id": pid,
            "doctor_id": doc_id,
            "nurse_id": nurse_id,
            "doc_headers": {"Authorization": f"Bearer {doc_token}", "X-Request-ID": "req-guard-doc"},
            "nurse_headers": {"Authorization": f"Bearer {nurse_token}", "X-Request-ID": "req-guard-nurse"},
        }


def test_untouched_ai_draft_to_memory_is_rejected(test_setup):
    """AI_GENERATED -> MEMORY directly without doctor edit or acknowledgment must be rejected."""
    pid = test_setup["patient_id"]
    headers = test_setup["doc_headers"]

    # 1. Create AI consultation draft
    res = client.post(f"/api/v1/patients/{pid}/consultations", json={"specialty": "cardiology"}, headers=headers)
    assert res.status_code == 201
    cns_data = res.json()["data"]
    cid = cns_data["id"]
    assert cns_data["version"]["origin"] == "ai_generated"

    # 2. Attempt to approve directly without doctor edit and without acknowledged_unedited
    with patch("app.validation.gate1_memory.evaluate_gate1_judge", return_value=(True, "info", {"passed": True})):
        appr_res = client.post(
            f"/api/v1/consultations/{cid}/approve",
            json={"acknowledged_unedited": False},
            headers=headers,
        )
        assert appr_res.status_code == 422
        assert "GATE1_BLOCKED" in appr_res.json()["error"]["code"]
        assert "AI-generated draft cannot be approved" in appr_res.json()["error"]["message"]


def test_preserves_original_ai_version_after_doctor_edits(test_setup):
    """The original AI-generated version (v1) must be preserved in version history after doctor edits."""
    pid = test_setup["patient_id"]
    headers = test_setup["doc_headers"]

    # 1. Create AI consultation draft (v1)
    res = client.post(f"/api/v1/patients/{pid}/consultations", json={"specialty": "general_medicine"}, headers=headers)
    assert res.status_code == 201
    cid = res.json()["data"]["id"]
    v1_id = res.json()["data"]["current_version_id"]

    # 2. Doctor updates draft
    edit_res = client.put(
        f"/api/v1/consultations/{cid}",
        json={
            "content": {
                "chief_complaint": "Hypertension review",
                "examination": "BP 130/84 mmHg, HR 72 regular",
                "assessment": "Stage 1 HTN well-controlled",
                "plan": "Continue current medications",
            },
            "expected_version_id": v1_id,
        },
        headers=headers,
    )
    assert edit_res.status_code == 200

    # 3. List all versions: v1 must remain origin='ai_generated' and intact!
    vers_res = client.get(f"/api/v1/consultations/{cid}/versions", headers=headers)
    assert vers_res.status_code == 200
    versions = vers_res.json()["data"]
    assert len(versions) == 2

    v1 = next(v for v in versions if v["version_number"] == 1)
    v2 = next(v for v in versions if v["version_number"] == 2)

    assert v1["origin"] == "ai_generated"
    assert v1["content"]["assessment"] == ""  # original empty clinician fields preserved!
    assert v2["origin"] == "doctor_edited"
    assert v2["content"]["assessment"] == "Stage 1 HTN well-controlled"


def test_approval_stores_doctor_id_version_id_timestamp_and_content_hash(test_setup):
    """Approval must capture doctor ID, consultation ID, version ID, timestamp, and content hash."""
    pid = test_setup["patient_id"]
    doc_id = test_setup["doctor_id"]
    headers = test_setup["doc_headers"]

    # 1. Create draft and edit
    res = client.post(f"/api/v1/patients/{pid}/consultations", json={"specialty": "cardiology"}, headers=headers)
    cid = res.json()["data"]["id"]
    v1_id = res.json()["data"]["current_version_id"]

    content = {
        "chief_complaint": "Chest pain on exertion",
        "examination": "Normal exam, heart sounds regular",
        "assessment": "Atypical angina pectoris",
        "plan": "Order stress echocardiogram and lipid profile",
    }
    client.put(
        f"/api/v1/consultations/{cid}",
        json={"content": content, "expected_version_id": v1_id},
        headers=headers,
    )

    # 2. Approve
    with patch("app.validation.gate1_memory.evaluate_gate1_judge", return_value=(True, "info", {"passed": True})):
        appr_res = client.post(
            f"/api/v1/consultations/{cid}/approve",
            json={"acknowledged_unedited": True},
            headers=headers,
        )
        assert appr_res.status_code == 200
        appr_data = appr_res.json()["data"]

        assert appr_data["status"] == "approved"
        assert appr_data["doctor_id"] == doc_id
        assert appr_data["consultation_id"] == cid
        assert "version_id" in appr_data
        assert "approval_timestamp" in appr_data
        assert "content_hash" in appr_data
        assert len(appr_data["content_hash"]) == 64  # Valid sha256 hex digest

    # 3. Verify memory provenance retains content_hash and doctor_id
    with get_db_context() as db:
        memories = db.query(ClinicalMemory).filter(ClinicalMemory.source_consultation_id == cid).all()
        assert len(memories) >= 2
        for mem in memories:
            prov = mem.provenance
            assert prov.get("doctor_id") == doc_id
            assert prov.get("consultation_id") == cid
            assert prov.get("content_hash") == appr_data["content_hash"]
            assert prov.get("approval_timestamp") == appr_data["approval_timestamp"]


def test_non_doctor_cannot_approve_clinical_information(test_setup):
    """Non-doctor users (e.g. nurse) cannot approve consultations or clinical facts into verified status."""
    pid = test_setup["patient_id"]
    nurse_headers = test_setup["nurse_headers"]
    doc_headers = test_setup["doc_headers"]

    # 1. Create a consultation
    c_res = client.post(f"/api/v1/patients/{pid}/consultations", json={"specialty": "general_medicine"}, headers=doc_headers)
    cid = c_res.json()["data"]["id"]

    # Attempt to approve as nurse -> 403 Forbidden
    appr_nurse = client.post(
        f"/api/v1/consultations/{cid}/approve",
        json={"acknowledged_unedited": True},
        headers=nurse_headers,
    )
    assert appr_nurse.status_code == 403

    # 2. Create unverified clinical fact
    with get_db_context() as db:
        fact = ClinicalFact(
            id=fact_id(),
            patient_id=pid,
            fact_type="diagnosis",
            value="Asthma",
            source_text="Asthma noted",
            provenance_verified=False,
            verification_status="unverified",
            confidence=0.6,
        )
        db.add(fact)
        db.commit()
        fid = fact.id

    # Attempt to mark fact as doctor_verified as nurse -> 403 Forbidden
    patch_nurse = client.patch(
        f"/api/v1/facts/{fid}",
        json={"verification_status": "doctor_verified", "doctor_note": "Nurse approved"},
        headers=nurse_headers,
    )
    assert patch_nurse.status_code == 403


def test_unverified_fact_cannot_become_approved_without_doctor_review(test_setup):
    """UNVERIFIED facts cannot transition to APPROVED without explicit doctor review (doctor_note or corrected_value)."""
    pid = test_setup["patient_id"]
    headers = test_setup["doc_headers"]

    with get_db_context() as db:
        fact = ClinicalFact(
            id=fact_id(),
            patient_id=pid,
            fact_type="medication",
            value="Lisinopril 10 mg",
            source_text="Lisinopril 10 mg daily",
            provenance_verified=False,
            verification_status="unverified",
            confidence=0.7,
        )
        db.add(fact)
        db.commit()
        fid = fact.id

    # Attempt to patch verification_status to APPROVED with empty note and no correction -> 409 InvalidStateTransitionError
    resp_empty = client.patch(
        f"/api/v1/facts/{fid}",
        json={"verification_status": "doctor_verified"},
        headers=headers,
    )
    assert resp_empty.status_code == 409
    assert resp_empty.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    # With doctor_note -> Success
    resp_valid = client.patch(
        f"/api/v1/facts/{fid}",
        json={"verification_status": "doctor_verified", "doctor_note": "Verified with pharmacy records"},
        headers=headers,
    )
    assert resp_valid.status_code == 200
    assert resp_valid.json()["data"]["verification_status"] == "doctor_verified"


def test_conflicting_fact_cannot_transition_to_current_until_resolved(test_setup):
    """CONFLICTING clinical facts cannot transition to CURRENT or APPROVED until resolved with doctor review."""
    pid = test_setup["patient_id"]
    headers = test_setup["doc_headers"]

    with get_db_context() as db:
        fact = ClinicalFact(
            id=fact_id(),
            patient_id=pid,
            fact_type="medication",
            value="Metformin 500 mg",
            source_text="Conflicting doses in chart",
            provenance_verified=False,
            verification_status="conflicting",
            confidence=0.5,
        )
        db.add(fact)
        db.commit()
        fid = fact.id

    # Attempt to change semantic_state to CURRENT without resolution note or correction -> 409 InvalidStateTransitionError
    resp_conflict = client.patch(
        f"/api/v1/facts/{fid}",
        json={"semantic_state": "DOCUMENTED"},
        headers=headers,
    )
    assert resp_conflict.status_code == 409
    assert resp_conflict.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    # Resolving with doctor note and corrected value -> Success
    resp_resolved = client.patch(
        f"/api/v1/facts/{fid}",
        json={
            "semantic_state": "DOCUMENTED",
            "corrected_value": "Metformin 500 mg BD",
            "doctor_note": "Resolved conflicting frequency with patient during interview: takes BD.",
        },
        headers=headers,
    )
    assert resp_resolved.status_code == 200
    assert resp_resolved.json()["data"]["semantic_state"] == "DOCUMENTED"
    assert resp_resolved.json()["data"]["value"] == "Metformin 500 mg BD"


def test_memory_proposal_conflicting_cannot_approve_until_resolved(test_setup):
    """CONFLICTING clinical memory proposal cannot transition to CURRENT until resolved."""
    pid = test_setup["patient_id"]
    headers = test_setup["doc_headers"]

    with get_db_context() as db:
        mem = ClinicalMemory(
            id=clinical_memory_id(),
            patient_id=pid,
            memory_type="medication",
            content_json=json.dumps({
                "content": "Metformin conflicting dose",
                "memory_state": "CONFLICTING",
                "semantic_state": "CONFLICTING",
            }),
            verified=False,
        )
        db.add(mem)
        db.commit()
        mid = mem.id

    # Attempt to approve without resolving -> 409 InvalidStateTransitionError
    resp = client.post(f"/api/v1/memories/{mid}/approve", headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    # Approve with resolution -> Success
    resp_ok = client.post(
        f"/api/v1/memories/{mid}/approve",
        json={"resolved": True, "doctor_note": "Reconciled with patient records"},
        headers=headers,
    )
    assert resp_ok.status_code == 200
    assert resp_ok.json()["data"]["verified"] is True
    assert resp_ok.json()["data"]["memory_state"] == "CURRENT"
    assert "content_hash" in resp_ok.json()["data"]
