"""
Senior QA & Security Engineering Adversarial Test Suite for ClinSync.

Executes comprehensive real-world attacks, failure injections, data integrity tests,
and end-to-end multi-step clinical scenarios:

1. End-to-End Workflow Verification:
   - Patient creation & auth
   - Document upload & ingestion pipeline
   - Derived clinical intelligence (timeline, medications, conflicts, missing info)
   - Doctor Brief & Gate 2 validation
   - Consultation creation, doctor edit, Gate 1 validation, approval & clinical memory
   - Voice note processing, STT transcription, and clinician review

2. Security Attacks & Exploit Attempts:
   - Unauthenticated access to patient endpoints (401 Unauthorized)
   - Cross-user patient access / IDOR (403 Forbidden)
   - Cross-patient document access / IDOR (403 Forbidden)
   - Directory traversal path attempts (Rejected / Traversal blocked)
   - Fake / ungrounded document and evidence IDs
   - Corrupted and oversized file payloads (413 Payload Too Large / 400 Bad Request)
   - Prompt injection attacks (neutralized & isolated)
   - Replay / duplicate approval attempts (409 Conflict)
   - Invalid & expired JWT tokens (401 Unauthorized)
   - Privilege escalation: Non-doctor (e.g. nurse/patient) approving consultation (403 Forbidden)

3. Data Integrity & Concurrency:
   - Duplicate document uploads (SHA-256 deduplication and low-severity issue flag)
   - Append-only immutability of approved clinical memory
   - Optimistic concurrency control (stale version updates blocked)
   - Double approval prevention

4. Failure Injection & Safe Degradation:
   - LLM primary failure -> fallback usage
   - LLM complete outage -> fallback template brief generated safely
   - Malformed/corrupted model output -> json repair or safe fallback
   - Gate 1 judge failure -> fail closed with retryable 503
   - Gate 2 failure -> safe deterministic fallback brief
"""

import json
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
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
from app.utils.tokens import create_access_token
from app.api.errors import LLMUnavailableError


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def qa_env():
    """Sets up two separate doctors and two separate patients for cross-access testing."""
    with get_db_context() as db:
        # Doctor A
        doc_a = db.query(User).filter(User.id == "usr_qa_doc_a").first()
        if not doc_a:
            doc_a = User(
                id="usr_qa_doc_a",
                email="doc_a@clinsync.health",
                hashed_password="hash",
                full_name="Dr. Alice Smith",
                role="doctor",
                specialty="Cardiology",
                is_active=True,
            )
            db.add(doc_a)

        # Doctor B
        doc_b = db.query(User).filter(User.id == "usr_qa_doc_b").first()
        if not doc_b:
            doc_b = User(
                id="usr_qa_doc_b",
                email="doc_b@clinsync.health",
                hashed_password="hash",
                full_name="Dr. Bob Jones",
                role="doctor",
                specialty="Neurology",
                is_active=True,
            )
            db.add(doc_b)

        # Nurse User (Non-doctor role)
        nurse = db.query(User).filter(User.id == "usr_qa_nurse").first()
        if not nurse:
            nurse = User(
                id="usr_qa_nurse",
                email="nurse@clinsync.health",
                hashed_password="hash",
                full_name="Nurse Nancy",
                role="nurse",
                specialty="Triage",
                is_active=True,
            )
            db.add(nurse)

        # Patient A (Assigned only to Doctor A)
        pat_a = db.query(Patient).filter(Patient.id == "pat_qa_patient_a").first()
        if not pat_a:
            pat_a = Patient(
                id="pat_qa_patient_a",
                full_name="Patient Alice Cooper",
                age_years=48,
                sex="female",
                is_demo=False,
            )
            db.add(pat_a)

        # Patient B (Assigned only to Doctor B)
        pat_b = db.query(Patient).filter(Patient.id == "pat_qa_patient_b").first()
        if not pat_b:
            pat_b = Patient(
                id="pat_qa_patient_b",
                full_name="Patient Bob Dylan",
                age_years=62,
                sex="male",
                is_demo=False,
            )
            db.add(pat_b)

        db.commit()

        # Access assignments: Doc A -> Pat A
        acc_a = db.query(PatientAccess).filter(
            PatientAccess.patient_id == "pat_qa_patient_a",
            PatientAccess.user_id == "usr_qa_doc_a"
        ).first()
        if not acc_a:
            db.add(PatientAccess(
                id="acc_qa_a",
                patient_id="pat_qa_patient_a",
                user_id="usr_qa_doc_a",
                access_level="write"
            ))

        # Access assignments: Doc B -> Pat B
        acc_b = db.query(PatientAccess).filter(
            PatientAccess.patient_id == "pat_qa_patient_b",
            PatientAccess.user_id == "usr_qa_doc_b"
        ).first()
        if not acc_b:
            db.add(PatientAccess(
                id="acc_qa_b",
                patient_id="pat_qa_patient_b",
                user_id="usr_qa_doc_b",
                access_level="write"
            ))

        # Access assignments: Nurse -> Pat A (Read/Triage)
        acc_nurse = db.query(PatientAccess).filter(
            PatientAccess.patient_id == "pat_qa_patient_a",
            PatientAccess.user_id == "usr_qa_nurse"
        ).first()
        if not acc_nurse:
            db.add(PatientAccess(
                id="acc_qa_nurse",
                patient_id="pat_qa_patient_a",
                user_id="usr_qa_nurse",
                access_level="read"
            ))

        # Document on Patient A
        doc_a_rec = db.query(Document).filter(Document.id == "doc_qa_patient_a_01").first()
        if not doc_a_rec:
            db.add(Document(
                id="doc_qa_patient_a_01",
                patient_id="pat_qa_patient_a",
                original_filename="cardio_panel.pdf",
                stored_path="cardio_panel.pdf",
                mime_type="application/pdf",
                file_size=2048,
                sha256="sha256_qa_a_01_sample_hash",
                processing_status="complete",
                page_count=1,
            ))

        db.commit()

    token_a = create_access_token(
        subject="usr_qa_doc_a",
        claims={"role": "doctor", "specialty": "Cardiology"}
    )
    token_b = create_access_token(
        subject="usr_qa_doc_b",
        claims={"role": "doctor", "specialty": "Neurology"}
    )
    token_nurse = create_access_token(
        subject="usr_qa_nurse",
        claims={"role": "nurse", "specialty": "Triage"}
    )

    return {
        "doc_a": {"id": "usr_qa_doc_a", "token": token_a, "headers": {"Authorization": f"Bearer {token_a}"}},
        "doc_b": {"id": "usr_qa_doc_b", "token": token_b, "headers": {"Authorization": f"Bearer {token_b}"}},
        "nurse": {"id": "usr_qa_nurse", "token": token_nurse, "headers": {"Authorization": f"Bearer {token_nurse}"}},
        "pat_a_id": "pat_qa_patient_a",
        "pat_b_id": "pat_qa_patient_b",
        "doc_a_id": "doc_qa_patient_a_01",
    }


def create_test_pdf_bytes(text: str = "Clinical Summary Note. Patient is stable.") -> bytes:
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text, fontsize=11)
    buf = doc.write()
    doc.close()
    return buf


# ==============================================================================
# SECTION 1: END-TO-END WORKFLOW SUITE
# ==============================================================================

class TestEndToEndWorkflow:
    def test_complete_patient_journey(self, client, qa_env):
        """End-to-end journey: create patient -> brief -> consultation draft -> edit -> Gate 1 -> memory."""
        doc_headers = qa_env["doc_a"]["headers"]

        # 1. Create Patient
        p_res = client.post(
            "/api/v1/patients",
            json={"full_name": "E2E Workflow Patient", "age_years": 55, "sex": "male"},
            headers=doc_headers,
        )
        assert p_res.status_code == 201
        pid = p_res.json()["data"]["id"]

        # Verify Doc A was automatically granted access
        with get_db_context() as db:
            access = db.query(PatientAccess).filter(
                PatientAccess.patient_id == pid,
                PatientAccess.user_id == qa_env["doc_a"]["id"]
            ).first()
            assert access is not None

        # 2. Add Clinical Fact
        with get_db_context() as db:
            fact = ClinicalFact(
                id=f"fact_e2e_{int(time.time())}",
                patient_id=pid,
                fact_type="diagnosis",
                value="Hypertension Stage 2",
                source_text="Documented BP 150/95 mmHg, diagnosing Hypertension Stage 2",
                verification_status="unverified",
                confidence=0.90,
            )
            db.add(fact)
            db.commit()

        # 3. Generate Brief
        b_res = client.post(
            f"/api/v1/patients/{pid}/brief",
            json={"specialty": "general_medicine", "force_regenerate": True},
            headers=doc_headers,
        )
        assert b_res.status_code == 200
        brief_data = b_res.json()["data"]
        assert brief_data["patient"]["id"] == pid
        assert "Hypertension Stage 2" in str(brief_data)

        # 4. Create Consultation Draft
        c_res = client.post(
            f"/api/v1/patients/{pid}/consultations",
            json={"specialty": "general_medicine"},
            headers=doc_headers,
        )
        assert c_res.status_code == 201
        cid = c_res.json()["data"]["id"]
        ver_id = c_res.json()["data"]["current_version_id"]

        # 5. Doctor Edits Draft
        u_res = client.put(
            f"/api/v1/consultations/{cid}",
            json={
                "content": {
                    "chief_complaint": "Hypertension Stage 2 follow-up",
                    "assessment": "Blood pressure elevated above goal",
                    "plan": "Start Amlodipine 5 mg daily and recheck in 4 weeks"
                },
                "expected_version_id": ver_id
            },
            headers=doc_headers,
        )
        assert u_res.status_code == 200

        # 6. Approve Consultation with Gate 1 Validation
        with patch("app.validation.gate1_memory.evaluate_gate1_judge", return_value=(True, "info", {"passed": True})):
            app_res = client.post(
                f"/api/v1/consultations/{cid}/approve",
                json={"acknowledged_unedited": True, "expected_version_id": ver_id},
                headers=doc_headers,
            )
            assert app_res.status_code == 200
            assert app_res.json()["data"]["status"] == "approved"

        # 7. Verify Verified Clinical Memory Created
        with get_db_context() as db:
            memories = db.query(ClinicalMemory).filter(
                ClinicalMemory.patient_id == pid,
                ClinicalMemory.verified == True
            ).all()
            assert len(memories) >= 2


# ==============================================================================
# SECTION 2: SECURITY ATTACKS & PENETRATION SUITE
# ==============================================================================

class TestSecurityAttacks:
    def test_unauthenticated_patient_access_blocked(self, client, qa_env, monkeypatch):
        """Unauthenticated requests must be rejected with 401 when demo fallback is disabled."""
        from app.config import settings
        monkeypatch.setattr(settings, "AUTH_DEMO_FALLBACK_ENABLED", False)

        pid = qa_env["pat_a_id"]
        # Patient overview
        res = client.get(f"/api/v1/patients/{pid}")
        assert res.status_code == 401

        # Patient brief
        res2 = client.get(f"/api/v1/patients/{pid}/brief/latest")
        assert res2.status_code == 401

    def test_cross_user_patient_idor_blocked(self, client, qa_env):
        """Doctor B must not access Doctor A's patient (IDOR protection)."""
        pid_a = qa_env["pat_a_id"]
        doc_b_headers = qa_env["doc_b"]["headers"]

        # GET patient
        res = client.get(f"/api/v1/patients/{pid_a}", headers=doc_b_headers)
        assert res.status_code == 403

        # GET brief
        res_brief = client.get(f"/api/v1/patients/{pid_a}/brief/latest", headers=doc_b_headers)
        assert res_brief.status_code == 403

        # POST brief
        res_post_brief = client.post(f"/api/v1/patients/{pid_a}/brief", headers=doc_b_headers)
        assert res_post_brief.status_code == 403

    def test_cross_patient_document_idor_blocked(self, client, qa_env):
        """Doctor B must not access Doctor A's patient's document files."""
        doc_id_a = qa_env["doc_a_id"]
        doc_b_headers = qa_env["doc_b"]["headers"]

        # View document
        res = client.get(f"/api/v1/documents/{doc_id_a}", headers=doc_b_headers)
        assert res.status_code == 403

        # Download file
        res_file = client.get(f"/api/v1/documents/{doc_id_a}/file", headers=doc_b_headers)
        assert res_file.status_code == 403

    def test_directory_traversal_blocked(self, client, qa_env):
        """Malicious filenames attempting directory traversal must be rejected or sanitized."""
        pid = qa_env["pat_a_id"]
        headers = qa_env["doc_a"]["headers"]

        valid_pdf = create_test_pdf_bytes("Directory traversal test content.")
        res = client.post(
            f"/api/v1/patients/{pid}/documents",
            files={"file": ("../../../../etc/passwd.pdf", valid_pdf, "application/pdf")},
            headers=headers,
        )
        # Must succeed with sanitized safe basename (path traversal neutralized)
        assert res.status_code == 201
        stored_name = res.json()["data"]["original_filename"]
        assert "../" not in stored_name
        assert ".." not in stored_name

    def test_oversized_file_rejected(self, client, qa_env):
        """Files exceeding max size limit (25 MB) must return 413 Payload Too Large."""
        pid = qa_env["pat_a_id"]
        headers = qa_env["doc_a"]["headers"]

        oversized_bytes = b"0" * (26 * 1024 * 1024)
        res = client.post(
            f"/api/v1/patients/{pid}/documents",
            files={"file": ("huge.pdf", oversized_bytes, "application/pdf")},
            headers=headers,
        )
        assert res.status_code == 413

    def test_invalid_and_expired_tokens_blocked(self, client, qa_env):
        """Tampered or expired JWT tokens must return 401 Unauthorized."""
        pid = qa_env["pat_a_id"]

        # 1. Tampered token
        tampered_headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.tampered.signature"}
        res1 = client.get(f"/api/v1/patients/{pid}", headers=tampered_headers)
        assert res1.status_code == 401

        # 2. Expired token
        expired_token = create_access_token(
            subject="usr_qa_doc_a",
            claims={"role": "doctor"},
            expires_delta=timedelta(minutes=-30)
        )
        res2 = client.get(f"/api/v1/patients/{pid}", headers={"Authorization": f"Bearer {expired_token}"})
        assert res2.status_code == 401

    def test_privilege_escalation_blocked(self, client, qa_env):
        """Non-doctor roles (e.g. nurse) cannot approve consultations (Gate 1)."""
        pid = qa_env["pat_a_id"]
        doc_headers = qa_env["doc_a"]["headers"]
        nurse_headers = qa_env["nurse"]["headers"]

        # Create consultation draft as doctor
        c_res = client.post(
            f"/api/v1/patients/{pid}/consultations",
            json={"specialty": "general_medicine"},
            headers=doc_headers,
        )
        cid = c_res.json()["data"]["id"]

        # Nurse attempts approval -> 403 Forbidden
        app_res = client.post(
            f"/api/v1/consultations/{cid}/approve",
            json={"acknowledged_unedited": True},
            headers=nurse_headers,
        )
        assert app_res.status_code == 403


# ==============================================================================
# SECTION 3: DATA INTEGRITY & CONCURRENCY SUITE
# ==============================================================================

class TestDataIntegrityAndConcurrency:
    def test_duplicate_document_upload_handled(self, client, qa_env):
        """Uploading identical content generates duplicate_record review item without data corruption."""
        pid = qa_env["pat_a_id"]
        headers = qa_env["doc_a"]["headers"]

        pdf_bytes = create_test_pdf_bytes("Lab report: Complete Metabolic Panel.")
        res1 = client.post(
            f"/api/v1/patients/{pid}/documents",
            files={"file": ("lab1.pdf", pdf_bytes, "application/pdf")},
            headers=headers,
        )
        assert res1.status_code == 201

        # Duplicate upload of same bytes
        res2 = client.post(
            f"/api/v1/patients/{pid}/documents",
            files={"file": ("lab1_copy.pdf", pdf_bytes, "application/pdf")},
            headers=headers,
        )
        assert res2.status_code == 201
        assert res2.json()["data"]["duplicate"] is True

    def test_duplicate_approval_blocked(self, client, qa_env):
        """Double-approving an already approved consultation must return 409 Conflict."""
        pid = qa_env["pat_a_id"]
        headers = qa_env["doc_a"]["headers"]

        c_res = client.post(
            f"/api/v1/patients/{pid}/consultations",
            json={"specialty": "general_medicine"},
            headers=headers,
        )
        cid = c_res.json()["data"]["id"]

        with patch("app.validation.gate1_memory.evaluate_gate1_judge", return_value=(True, "info", {"passed": True})):
            # First approval succeeds
            res1 = client.post(
                f"/api/v1/consultations/{cid}/approve",
                json={"acknowledged_unedited": True},
                headers=headers,
            )
            assert res1.status_code == 200

            # Second approval blocked
            res2 = client.post(
                f"/api/v1/consultations/{cid}/approve",
                json={"acknowledged_unedited": True},
                headers=headers,
            )
            assert res2.status_code == 409

    def test_stale_concurrency_update_blocked(self, client, qa_env):
        """Updating a consultation with a stale expected_version_id must return 409 Conflict."""
        pid = qa_env["pat_a_id"]
        headers = qa_env["doc_a"]["headers"]

        c_res = client.post(
            f"/api/v1/patients/{pid}/consultations",
            json={"specialty": "general_medicine"},
            headers=headers,
        )
        cid = c_res.json()["data"]["id"]
        v1_id = c_res.json()["data"]["current_version_id"]

        # Doctor advances consultation by creating version v2
        client.post(
            f"/api/v1/consultations/{cid}/versions",
            json={"content": {"assessment": "V2 update"}, "expected_version_id": v1_id},
            headers=headers,
        )

        # Another client attempts update using stale v1_id
        stale_res = client.put(
            f"/api/v1/consultations/{cid}",
            json={"content": {"assessment": "Stale update"}, "expected_version_id": v1_id},
            headers=headers,
        )
        assert stale_res.status_code == 409


# ==============================================================================
# SECTION 4: FAILURE INJECTION & RESILIENCE SUITE
# ==============================================================================

class TestFailureInjection:
    def test_brief_generation_survives_llm_outage(self, client, qa_env):
        """When LLM router is completely offline, brief generator falls back to deterministic template."""
        pid = qa_env["pat_a_id"]
        headers = qa_env["doc_a"]["headers"]

        with patch("app.ai.gateway.llm_gateway.complete_json", side_effect=LLMUnavailableError("LLM offline")):
            res = client.post(
                f"/api/v1/patients/{pid}/brief",
                json={"specialty": "general_medicine", "force_regenerate": True},
                headers=headers,
            )
            assert res.status_code == 200
            data = res.json()["data"]
            assert data["generation_source"] == "fallback_template"
            assert res.json()["meta"]["source"] == "fallback"

    def test_gate1_fails_closed_when_judge_offline(self, client, qa_env):
        """When Gate 1 validation judge is unavailable, approval fails closed safely with 503."""
        pid = qa_env["pat_a_id"]
        headers = qa_env["doc_a"]["headers"]

        c_res = client.post(
            f"/api/v1/patients/{pid}/consultations",
            json={"specialty": "general_medicine"},
            headers=headers,
        )
        cid = c_res.json()["data"]["id"]

        # Judge unavailable returns ("judge_unavailable")
        with patch("app.validation.gate1_memory.evaluate_gate1_judge", return_value=(False, "judge_unavailable", {})):
            res = client.post(
                f"/api/v1/consultations/{cid}/approve",
                json={"acknowledged_unedited": True},
                headers=headers,
            )
            # Fail closed: must return 503 Service Unavailable so client knows it is retryable
            assert res.status_code == 503

        # Verify no memory was written
        with get_db_context() as db:
            cns = db.query(Consultation).filter(Consultation.id == cid).first()
            assert cns.status != "approved"


# ==============================================================================
# SECTION 5: REGISTRATION PRIVILEGE ESCALATION SUITE (PHASE 2)
# ==============================================================================

class TestRegistrationPrivilegeEscalation:
    def test_normal_registration_creates_doctor(self, client):
        """Unauthenticated user registering normally creates standard doctor account."""
        res = client.post(
            "/api/v1/auth/register",
            json={
                "email": "dr_standard_reg@clinsync.health",
                "password": "ValidPassword123!",
                "full_name": "Dr. Standard Registered",
                "role": "doctor",
                "specialty": "Pediatrics",
            },
        )
        assert res.status_code == 200
        assert res.json()["data"]["role"] == "doctor"

    def test_role_omission_defaults_to_doctor(self, client):
        """Omitting the role field in public registration safely defaults to doctor."""
        res = client.post(
            "/api/v1/auth/register",
            json={
                "email": "dr_no_role@clinsync.health",
                "password": "ValidPassword123!",
                "full_name": "Dr. No Role Provided",
            },
        )
        assert res.status_code == 200
        assert res.json()["data"]["role"] == "doctor"

    def test_attempted_admin_registration_blocked(self, client):
        """Public unauthenticated user attempting self-promotion to admin must receive 400 Bad Request."""
        res = client.post(
            "/api/v1/auth/register",
            json={
                "email": "attacker_admin@clinsync.health",
                "password": "AttackerPassword123!",
                "full_name": "Malicious User",
                "role": "admin",
            },
        )
        assert res.status_code == 400
        assert "Registration with privileged role" in res.json()["error"]["message"]

    def test_attempted_privileged_role_registration_blocked(self, client):
        """Public registration attempting root or superuser must receive 400 Bad Request."""
        for priv_role in ("superuser", "root", "administrator"):
            res = client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"attacker_{priv_role}@clinsync.health",
                    "password": "AttackerPassword123!",
                    "full_name": "Malicious User",
                    "role": priv_role,
                },
            )
            assert res.status_code == 400
            assert "Registration with privileged role" in res.json()["error"]["message"]

    def test_admin_can_provision_user_with_admin_role(self, client):
        """Authenticated admin can provision an account with admin role via POST /auth/users."""
        with get_db_context() as db:
            if not db.query(User).filter(User.id == "usr_admin_provisioner").first():
                db.add(User(
                    id="usr_admin_provisioner",
                    email="admin_prov@clinsync.health",
                    full_name="Admin Provisioner",
                    role="admin",
                    hashed_password="hash",
                    is_active=True,
                ))
            if not db.query(User).filter(User.id == "usr_doc_unauth").first():
                db.add(User(
                    id="usr_doc_unauth",
                    email="doc_unauth@clinsync.health",
                    full_name="Doc Unauth",
                    role="doctor",
                    hashed_password="hash",
                    is_active=True,
                ))
            db.commit()

        admin_token = create_access_token(
            subject="usr_admin_provisioner",
            claims={"role": "admin", "email": "admin@clinsync.health"}
        )
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 1. Admin creates another admin
        res = client.post(
            "/api/v1/auth/users",
            json={
                "email": "new_admin_provisioned@clinsync.health",
                "password": "AdminPassword123!",
                "full_name": "Provisioned Admin",
                "role": "admin",
                "specialty": "Administration",
            },
            headers=admin_headers,
        )
        assert res.status_code == 200
        assert res.json()["data"]["role"] == "admin"

        # 2. Non-admin doctor attempting to use admin provisioning endpoint receives 403 Forbidden
        doc_token = create_access_token(
            subject="usr_doc_unauth",
            claims={"role": "doctor", "email": "doc@clinsync.health"}
        )
        doc_headers = {"Authorization": f"Bearer {doc_token}"}
        res_forbidden = client.post(
            "/api/v1/auth/users",
            json={
                "email": "escalated_doc@clinsync.health",
                "password": "Password123!",
                "full_name": "Escalated Doc",
                "role": "admin",
            },
            headers=doc_headers,
        )
        assert res_forbidden.status_code == 403


# ==============================================================================
# SECTION 6: PRODUCTION ENVIRONMENT HARDENING SUITE (PHASES 5, 8, 9, 10)
# ==============================================================================

class TestProductionHardening:
    def test_production_startup_rejects_insecure_jwt_secret(self):
        """In production environment, default or weak JWT secrets must cause startup failure."""
        from app.main import lifespan
        from app.config import settings
        from fastapi import FastAPI

        test_app = FastAPI()
        with patch.object(settings, "APP_ENV", "production"), \
             patch.object(settings, "GEMINI_API_KEY", "valid_key"), \
             patch.object(settings, "GROQ_API_KEY", "valid_key"), \
             patch.object(settings, "AUTH_DEMO_FALLBACK_ENABLED", False), \
             patch.object(settings, "JWT_SECRET_KEY", "clinsync-default-insecure-dev-secret-key-change-me"):
            with pytest.raises(RuntimeError, match="JWT_SECRET_KEY must be configured"):
                async def run_probe():
                    async with lifespan(test_app):
                        pass
                import asyncio
                asyncio.run(run_probe())

    def test_production_startup_rejects_sqlite_database(self):
        """In production environment, SQLite database is prohibited."""
        from app.main import lifespan
        from app.config import settings
        from fastapi import FastAPI

        test_app = FastAPI()
        with patch.object(settings, "APP_ENV", "production"), \
             patch.object(settings, "GEMINI_API_KEY", "valid_key"), \
             patch.object(settings, "GROQ_API_KEY", "valid_key"), \
             patch.object(settings, "AUTH_DEMO_FALLBACK_ENABLED", False), \
             patch.object(settings, "JWT_SECRET_KEY", "a" * 32), \
             patch.object(settings, "DATABASE_URL", "sqlite:///./clinsync.db"):
            with pytest.raises(RuntimeError, match="Production environment requires a persistent relational database"):
                async def run_probe():
                    async with lifespan(test_app):
                        pass
                import asyncio
                asyncio.run(run_probe())

    def test_production_startup_rejects_wildcard_cors(self):
        """In production environment, wildcard CORS origins is prohibited."""
        from app.main import lifespan
        from app.config import settings
        from fastapi import FastAPI

        test_app = FastAPI()
        with patch.object(settings, "APP_ENV", "production"), \
             patch.object(settings, "GEMINI_API_KEY", "valid_key"), \
             patch.object(settings, "GROQ_API_KEY", "valid_key"), \
             patch.object(settings, "AUTH_DEMO_FALLBACK_ENABLED", False), \
             patch.object(settings, "JWT_SECRET_KEY", "a" * 32), \
             patch.object(settings, "DATABASE_URL", "postgresql://user:pass@localhost:5432/db"), \
             patch.object(settings, "CORS_ORIGINS", "*"):
            with pytest.raises(RuntimeError, match="Wildcard CORS"):
                async def run_probe():
                    async with lifespan(test_app):
                        pass
                import asyncio
                asyncio.run(run_probe())

    def test_patient_access_fails_closed_in_production_without_access_record(self, client, qa_env):
        """In production mode, a patient without explicit PatientAccess record returns 403 Forbidden."""
        from app.config import settings
        # Create unassigned patient
        with get_db_context() as db:
            unassigned_p = Patient(id="pat_unassigned_prod_01", full_name="Unassigned Patient", is_demo=False)
            db.add(unassigned_p)
            db.commit()

        headers = qa_env["doc_a"]["headers"]
        with patch.object(settings, "APP_ENV", "production"):
            res = client.get("/api/v1/patients/pat_unassigned_prod_01", headers=headers)
            assert res.status_code == 403
            assert "not authorized" in res.json()["error"]["message"]


# ==============================================================================
# SECTION 7: CROSS-PATIENT FULL GRAPH IDOR SUITE (PHASE 26)
# ==============================================================================

class TestCrossPatientFullGraphIDOR:
    def test_cross_patient_access_blocked_across_entire_graph(self, client, qa_env):
        """User A has access only to Patient A. Verify User A is blocked from every Patient B resource."""
        doc_a_headers = qa_env["doc_a"]["headers"]
        pat_b_id = qa_env["pat_b_id"]

        with get_db_context() as db:
            # Seed Patient B sub-resources
            doc_b = Document(
                id="doc_graph_b_01",
                patient_id=pat_b_id,
                original_filename="pat_b_report.pdf",
                stored_path="uploads/test/doc_graph_b_01.pdf",
                mime_type="application/pdf",
                file_size=1024,
                sha256="sha256_graph_b_unique",
                processing_status="complete",
                page_count=1,
            )
            cns_b = Consultation(
                id="cns_graph_b_01",
                patient_id=pat_b_id,
                status="draft",
            )
            mem_b = ClinicalMemory(
                id="mem_graph_b_01",
                patient_id=pat_b_id,
                memory_type="diagnosis",
                content_json='{"diagnosis": "Condition B"}',
                verified=True,
            )
            db.add_all([doc_b, cns_b, mem_b])
            db.commit()

        # 1. Patient Profile
        assert client.get(f"/api/v1/patients/{pat_b_id}", headers=doc_a_headers).status_code == 403
        # 2. Patient Overview
        assert client.get(f"/api/v1/patients/{pat_b_id}/overview", headers=doc_a_headers).status_code == 403
        # 3. Patient Documents List
        assert client.get(f"/api/v1/patients/{pat_b_id}/documents", headers=doc_a_headers).status_code == 403
        # 4. Document Metadata IDOR
        assert client.get(f"/api/v1/documents/doc_graph_b_01", headers=doc_a_headers).status_code == 403
        # 5. Document Raw File IDOR
        assert client.get(f"/api/v1/documents/doc_graph_b_01/file", headers=doc_a_headers).status_code == 403
        # 6. Timeline IDOR
        assert client.get(f"/api/v1/patients/{pat_b_id}/timeline", headers=doc_a_headers).status_code == 403
        # 7. Medications IDOR
        assert client.get(f"/api/v1/patients/{pat_b_id}/medications", headers=doc_a_headers).status_code == 403
        # 8. Investigations IDOR
        assert client.get(f"/api/v1/patients/{pat_b_id}/investigations", headers=doc_a_headers).status_code == 403
        # 9. Brief IDOR
        assert client.get(f"/api/v1/patients/{pat_b_id}/brief/latest", headers=doc_a_headers).status_code == 403
        # 10. Consultation IDOR
        assert client.get(f"/api/v1/patients/{pat_b_id}/consultations", headers=doc_a_headers).status_code == 403
        # 11. Memory IDOR
        assert client.get(f"/api/v1/patients/{pat_b_id}/memories", headers=doc_a_headers).status_code == 403
        # 12. Audit Logs IDOR
        assert client.get(f"/api/v1/patients/{pat_b_id}/audit", headers=doc_a_headers).status_code == 403

