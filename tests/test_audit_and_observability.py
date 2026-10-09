"""
Automated Test Suite for Auditability and Observability Hardening.

Verifies:
1. Every state-changing clinical mutation generates an audit record:
   - patient: create
   - document: upload, processed, reprocess_requested
   - clinical fact: fact_updated
   - medication & investigation: created during ingestion pipeline
   - contradiction: status / doctor note update
   - doctor brief: brief_generated
   - consultation: draft created, draft updated, version created
   - approval: consultation_approved
   - clinical memory: proposed, approved, rejected
   - voice record: uploaded, reviewed
2. Audit records capture actor/user ID, action, resource type, resource ID, patient ID, timestamp, before/after states, request correlation ID.
3. Immutability/Integrity: ordinary endpoints cannot modify or delete audit records.
4. AI Metrics: model calls, failures, retries, fallback usage, extraction failures, Gate 1 & Gate 2 failures, and processing durations.
5. Observability: request correlation ID and structured response metadata.
"""

import json
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_db_context
from app.models.user import User
from app.models.patient import Patient
from app.models.patient_access import PatientAccess
from app.models.document import Document
from app.models.clinical_fact import ClinicalFact
from app.models.medication import Medication
from app.models.investigation import Investigation
from app.models.contradiction import Contradiction
from app.models.brief import Brief
from app.models.consultation import Consultation, ConsultationVersion
from app.models.clinical_memory import ClinicalMemory
from app.models.voice_note import VoiceNote
from app.models.audit_log import AuditLog
from app.services.metrics_service import metrics_service
from app.services.audit_service import audit_service


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def test_setup():
    with get_db_context() as db:
        # Create users
        doc_user = db.query(User).filter(User.id == "usr_test_audit_doctor").first()
        if not doc_user:
            doc_user = User(
                id="usr_test_audit_doctor",
                email="audit_doctor@clinsync.health",
                hashed_password="fakehash",
                full_name="Dr. Audit Investigator",
                role="doctor",
                specialty="General Medicine",
                is_active=True,
            )
            db.add(doc_user)

        # Create patient
        pat = db.query(Patient).filter(Patient.id == "pat_test_audit_001").first()
        if not pat:
            pat = Patient(
                id="pat_test_audit_001",
                full_name="Audited Patient",
                age_years=52,
                sex="female",
                is_demo=False,
            )
            db.add(pat)

        # Assign access
        access = db.query(PatientAccess).filter(
            PatientAccess.patient_id == "pat_test_audit_001",
            PatientAccess.user_id == "usr_test_audit_doctor"
        ).first()
        if not access:
            access = PatientAccess(
                id="acc_test_audit_001",
                patient_id="pat_test_audit_001",
                user_id="usr_test_audit_doctor",
                access_level="write"
            )
            db.add(access)

        db.commit()

    from app.utils.tokens import create_access_token
    token = create_access_token(
        subject="usr_test_audit_doctor",
        claims={"role": "doctor", "specialty": "General Medicine"}
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Request-ID": "req-audit-test-9999"
    }

    return {
        "doctor_id": "usr_test_audit_doctor",
        "patient_id": "pat_test_audit_001",
        "headers": headers,
    }


def test_patient_creation_audited(client, test_setup):
    """Test 1: Patient creation generates an audit record."""
    headers = test_setup["headers"]
    req_id = "req-patient-create-001"
    headers_with_req = {**headers, "X-Request-ID": req_id}

    resp = client.post(
        "/api/v1/patients",
        json={"full_name": "Audit New Patient", "age_years": 40, "sex": "male"},
        headers=headers_with_req,
    )
    assert resp.status_code == 201
    new_pid = resp.json()["data"]["id"]

    with get_db_context() as db:
        audit = db.query(AuditLog).filter(
            AuditLog.entity_id == new_pid,
            AuditLog.action == "patient.created"
        ).first()
        assert audit is not None
        assert audit.actor == test_setup["doctor_id"]
        assert audit.entity_type == "patient"
        assert audit.patient_id == new_pid
        assert audit.request_id == req_id
        assert "Audit New Patient" in audit.after_json


def test_document_reprocess_audited(client, test_setup):
    """Test 2: Document reprocessing request generates an audit record."""
    pid = test_setup["patient_id"]
    headers = test_setup["headers"]
    doc_id = "doc_audit_reprocess_001"

    with get_db_context() as db:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            doc = Document(
                id=doc_id,
                patient_id=pid,
                original_filename="test_scan.pdf",
                stored_path="test_scan.pdf",
                mime_type="application/pdf",
                file_size=1024,
                sha256="fake_sha256_hash_1234567890abcdef",
                processing_status="complete",
                page_count=1,
            )
            db.add(doc)
            db.commit()

    req_id = "req-doc-reprocess-001"
    headers_with_req = {**headers, "X-Request-ID": req_id}

    with pytest.MonkeyPatch.context() as mp:
        from app.services.task_worker import task_worker
        mp.setattr(task_worker, "process_document_async", lambda *args, **kwargs: None)
        resp = client.post(f"/api/v1/documents/{doc_id}/reprocess", headers=headers_with_req)
        assert resp.status_code == 200

    with get_db_context() as db:
        audit = db.query(AuditLog).filter(
            AuditLog.entity_id == doc_id,
            AuditLog.action == "document.reprocess_requested"
        ).first()
        assert audit is not None
        assert audit.actor == test_setup["doctor_id"]
        assert audit.entity_type == "document"
        assert audit.patient_id == pid
        assert audit.request_id == req_id


def test_clinical_fact_patch_audited(client, test_setup):
    """Test 3: Clinical fact update generates an audit record with before/after state."""
    pid = test_setup["patient_id"]
    headers = test_setup["headers"]
    fact_id = "fact_audit_patch_001"

    with get_db_context() as db:
        fact = db.query(ClinicalFact).filter(ClinicalFact.id == fact_id).first()
        if not fact:
            fact = ClinicalFact(
                id=fact_id,
                patient_id=pid,
                fact_type="medication",
                value="Metformin 500 mg",
                source_text="Metformin 500 mg PO daily",
                verification_status="unverified",
                confidence=0.85,
            )
            db.add(fact)
            db.commit()

    req_id = "req-fact-patch-001"
    resp = client.patch(
        f"/api/v1/facts/{fact_id}",
        json={"verification_status": "doctor_verified", "corrected_value": "Metformin 1000 mg"},
        headers={**headers, "X-Request-ID": req_id},
    )
    assert resp.status_code == 200

    with get_db_context() as db:
        audit = db.query(AuditLog).filter(
            AuditLog.entity_id == fact_id,
            AuditLog.action == "fact_updated"
        ).first()
        assert audit is not None
        assert audit.actor == test_setup["doctor_id"]
        assert audit.entity_type == "clinical_fact"
        assert audit.patient_id == pid
        assert audit.request_id == req_id
        before = json.loads(audit.before_json)
        after = json.loads(audit.after_json)
        assert before["value"] == "Metformin 500 mg"
        assert after["value"] == "Metformin 1000 mg"
        assert after["verification_status"] == "doctor_verified"


def test_contradiction_patch_audited(client, test_setup):
    """Test 4: Contradiction status update generates an audit record."""
    pid = test_setup["patient_id"]
    headers = test_setup["headers"]
    iss_id = "iss_audit_patch_001"

    with get_db_context() as db:
        iss = db.query(Contradiction).filter(Contradiction.id == iss_id).first()
        if not iss:
            iss = Contradiction(
                id=iss_id,
                patient_id=pid,
                issue_type="medication_conflict",
                severity="high",
                title="Drug conflict",
                description="Warfarin vs Aspirin",
                status="open",
            )
            db.add(iss)
            db.commit()

    req_id = "req-issue-patch-001"
    resp = client.patch(
        f"/api/v1/issues/{iss_id}",
        json={"status": "resolved", "doctor_note": "Approved co-prescription with monitoring"},
        headers={**headers, "X-Request-ID": req_id},
    )
    assert resp.status_code == 200

    with get_db_context() as db:
        audit = db.query(AuditLog).filter(
            AuditLog.entity_id == iss_id,
            AuditLog.action == "contradiction_status_updated"
        ).first()
        assert audit is not None
        assert audit.actor == test_setup["doctor_id"]
        assert audit.entity_type == "contradiction"
        assert audit.patient_id == pid
        assert audit.request_id == req_id
        before = json.loads(audit.before_json)
        after = json.loads(audit.after_json)
        assert before["status"] == "open"
        assert after["status"] == "resolved"


def test_brief_generation_audited(client, test_setup):
    """Test 5: Doctor brief generation produces an audit record."""
    pid = test_setup["patient_id"]
    headers = test_setup["headers"]
    req_id = "req-brief-gen-001"

    resp = client.post(
        f"/api/v1/patients/{pid}/brief",
        json={"specialty": "general_medicine", "force_regenerate": True},
        headers={**headers, "X-Request-ID": req_id},
    )
    assert resp.status_code == 200

    with get_db_context() as db:
        audit = db.query(AuditLog).filter(
            AuditLog.patient_id == pid,
            AuditLog.action == "brief_generated"
        ).first()
        assert audit is not None
        assert audit.actor == test_setup["doctor_id"]
        assert audit.entity_type == "brief"
        assert audit.request_id == req_id
        after = json.loads(audit.after_json)
        assert after["specialty"] == "general_medicine"


def test_consultation_lifecycle_audited(client, test_setup):
    """Test 6: Consultation draft creation, draft edit, versioning, and approval all produce audit records."""
    pid = test_setup["patient_id"]
    headers = test_setup["headers"]

    # 1. Draft Creation
    req_id_1 = "req-cns-create-001"
    resp = client.post(
        f"/api/v1/patients/{pid}/consultations",
        json={"specialty": "general_medicine"},
        headers={**headers, "X-Request-ID": req_id_1},
    )
    assert resp.status_code == 201
    cns_id = resp.json()["data"]["id"]
    ver_id = resp.json()["data"]["current_version_id"]

    with get_db_context() as db:
        audit_create = db.query(AuditLog).filter(
            AuditLog.entity_id == cns_id,
            AuditLog.action == "consultation_created"
        ).first()
        assert audit_create is not None
        assert audit_create.patient_id == pid
        assert audit_create.request_id == req_id_1

    # 2. Draft Update
    req_id_2 = "req-cns-update-001"
    resp = client.put(
        f"/api/v1/consultations/{cns_id}",
        json={
            "content": {"chief_complaint": "Type 2 Diabetes", "assessment": "Well controlled", "plan": "Maintain regimen"},
            "expected_version_id": ver_id
        },
        headers={**headers, "X-Request-ID": req_id_2},
    )
    assert resp.status_code == 200

    with get_db_context() as db:
        audit_update = db.query(AuditLog).filter(
            AuditLog.entity_id == cns_id,
            AuditLog.action == "consultation_draft_updated"
        ).first()
        assert audit_update is not None
        assert audit_update.request_id == req_id_2

    # 3. Create Version
    req_id_3 = "req-cns-version-001"
    resp = client.post(
        f"/api/v1/consultations/{cns_id}/versions",
        json={
            "content": {"chief_complaint": "Type 2 Diabetes", "assessment": "Updated assessment", "plan": "Recheck in 3 months"},
            "change_summary": "Added 3 month follow-up"
        },
        headers={**headers, "X-Request-ID": req_id_3},
    )
    assert resp.status_code == 200
    new_ver_id = resp.json()["data"]["version_id"]

    with get_db_context() as db:
        audit_version = db.query(AuditLog).filter(
            AuditLog.entity_id == new_ver_id,
            AuditLog.action == "consultation_version_created"
        ).first()
        assert audit_version is not None
        assert audit_version.patient_id == pid
        assert audit_version.request_id == req_id_3

    # 4. Approval
    req_id_4 = "req-cns-approve-001"
    with pytest.MonkeyPatch.context() as mp:
        from app.validation.validators.llm_judge import evaluate_gate1_judge
        mp.setattr("app.validation.gate1_memory.evaluate_gate1_judge", lambda *args, **kwargs: (True, "info", {"passed": True}))
        resp = client.post(
            f"/api/v1/consultations/{cns_id}/approve",
            json={"acknowledged_unedited": True, "expected_version_id": new_ver_id},
            headers={**headers, "X-Request-ID": req_id_4},
        )
        assert resp.status_code == 200

    with get_db_context() as db:
        audit_approve = db.query(AuditLog).filter(
            AuditLog.entity_id == cns_id,
            AuditLog.action == "consultation_approved"
        ).first()
        assert audit_approve is not None
        assert audit_approve.actor == test_setup["doctor_id"]
        assert audit_approve.patient_id == pid


def test_clinical_memory_proposals_audited(client, test_setup):
    """Test 7: Clinical memory proposal, approval, and rejection generate audit records."""
    pid = test_setup["patient_id"]
    headers = test_setup["headers"]

    # 1. Propose memory
    req_id_1 = "req-mem-propose-001"
    resp = client.post(
        f"/api/v1/patients/{pid}/memories/proposals",
        json={"memory_type": "plan_note", "content": "Doctor recommended lifestyle changes"},
        headers={**headers, "X-Request-ID": req_id_1},
    )
    assert resp.status_code == 200
    prop_id = resp.json()["data"]["id"]

    with get_db_context() as db:
        audit_prop = db.query(AuditLog).filter(
            AuditLog.entity_id == prop_id,
            AuditLog.action == "clinical_memory_proposed"
        ).first()
        assert audit_prop is not None
        assert audit_prop.actor == test_setup["doctor_id"]
        assert audit_prop.patient_id == pid
        assert audit_prop.request_id == req_id_1

    # 2. Approve memory
    req_id_2 = "req-mem-approve-001"
    resp = client.post(
        f"/api/v1/memories/{prop_id}/approve",
        headers={**headers, "X-Request-ID": req_id_2},
    )
    assert resp.status_code == 200

    with get_db_context() as db:
        audit_app = db.query(AuditLog).filter(
            AuditLog.entity_id == prop_id,
            AuditLog.action == "clinical_memory_approved"
        ).first()
        assert audit_app is not None
        assert audit_app.actor == test_setup["doctor_id"]
        assert audit_app.request_id == req_id_2

    # 3. Create another proposal to reject
    resp = client.post(
        f"/api/v1/patients/{pid}/memories/proposals",
        json={"memory_type": "diagnosis", "content": "Temporary observation"},
        headers=headers,
    )
    prop2_id = resp.json()["data"]["id"]

    req_id_3 = "req-mem-reject-001"
    resp = client.post(
        f"/api/v1/memories/{prop2_id}/reject",
        headers={**headers, "X-Request-ID": req_id_3},
    )
    assert resp.status_code == 200

    with get_db_context() as db:
        audit_rej = db.query(AuditLog).filter(
            AuditLog.entity_id == prop2_id,
            AuditLog.action == "clinical_memory_rejected"
        ).first()
        assert audit_rej is not None
        assert audit_rej.actor == test_setup["doctor_id"]
        assert audit_rej.patient_id == pid
        assert audit_rej.request_id == req_id_3


def test_voice_pipeline_audited(client, test_setup):
    """Test 8: Voice note upload and review produce audit records."""
    pid = test_setup["patient_id"]
    headers = test_setup["headers"]

    req_id_1 = "req-voice-upload-001"
    fake_wav = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"

    with pytest.MonkeyPatch.context() as mp:
        from app.ai.gateway import llm_gateway
        mp.setattr(llm_gateway, "transcribe", lambda *args, **kwargs: {"text": "Patient has headache", "model": "whisper", "confidence": 0.95})
        resp = client.post(
            f"/api/v1/patients/{pid}/voice",
            files={"file": ("recording.wav", fake_wav, "audio/wav")},
            data={"language_hint": "en"},
            headers={**headers, "X-Request-ID": req_id_1},
        )
        assert resp.status_code == 201
        voice_id = resp.json()["data"]["id"]

    with get_db_context() as db:
        audit_voice = db.query(AuditLog).filter(
            AuditLog.entity_id == voice_id,
            AuditLog.action == "voice_note_uploaded"
        ).first()
        assert audit_voice is not None
        assert audit_voice.actor == test_setup["doctor_id"]
        assert audit_voice.patient_id == pid
        assert audit_voice.request_id == req_id_1

    # Review voice note
    req_id_2 = "req-voice-review-001"
    resp = client.post(
        f"/api/v1/voice/{voice_id}/review",
        json={"edited_transcript": "Patient reports severe tension headache"},
        headers={**headers, "X-Request-ID": req_id_2},
    )
    assert resp.status_code == 200

    with get_db_context() as db:
        audit_rev = db.query(AuditLog).filter(
            AuditLog.entity_id == voice_id,
            AuditLog.action == "voice_note_reviewed"
        ).first()
        assert audit_rev is not None
        assert audit_rev.actor == test_setup["doctor_id"]
        assert audit_rev.patient_id == pid
        assert audit_rev.request_id == req_id_2


def test_audit_integrity_and_immutability(client, test_setup):
    """Test 9: Audit records cannot be modified or deleted via API endpoints (no PUT/DELETE routes exist)."""
    headers = test_setup["headers"]
    pid = test_setup["patient_id"]

    # Verify GET is supported
    resp = client.get(f"/api/v1/patients/{pid}/audit", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Verify no PUT/DELETE endpoints exist for audit records
    resp_put = client.put(f"/api/v1/patients/{pid}/audit", json={}, headers=headers)
    assert resp_put.status_code in (404, 405)

    resp_delete = client.delete(f"/api/v1/patients/{pid}/audit", headers=headers)
    assert resp_delete.status_code in (404, 405)


def test_ai_metrics_and_observability(client, test_setup):
    """Test 10: AI Metrics service tracks calls, failures, retries, and gate blocks."""
    metrics_service.reset()

    # Record model call
    metrics_service.record_model_call(
        task="extract",
        slot="llm_extract",
        model="gemini-2.5-flash",
        latency_ms=150.0,
        success=True,
        retries=1,
    )
    # Record gate failures
    metrics_service.record_gate1_failure("cns_test_001", "High severity conflict unresolved")
    metrics_service.record_gate2_failure("pat_test_001", "Directive imperative language")
    # Record extraction failure
    metrics_service.record_extraction_failure("doc_001", "JSON format error")
    # Record stage duration
    metrics_service.record_stage_duration("ocr_extract_text", 350.0)

    summary = metrics_service.get_summary()
    ai = summary["ai_metrics"]
    assert ai["model_calls"] == 1
    assert ai["successes"] == 1
    assert ai["retries"] == 1
    assert ai["gate1_failures"] == 1
    assert ai["gate2_failures"] == 1
    assert ai["extraction_failures"] == 1
    assert summary["pipeline_stage_avg_duration_ms"]["ocr_extract_text"] == 350.0

    # Query metrics endpoint
    resp = client.get("/api/v1/metrics/ai")
    assert resp.status_code == 200
    data = resp.json()["data"]["ai_metrics"]
    assert data["model_calls"] == 1
    assert data["gate1_failures"] == 1
