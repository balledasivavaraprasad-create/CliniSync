"""Comprehensive test suite for authorization, patient data isolation, and IDOR prevention.

Tests verify:
1. Authorized patient access (doctor assigned to patient)
2. Unauthorized patient access / IDOR (doctor NOT assigned to patient -> 403 Forbidden)
3. Admin role bypass (admin can access any patient record)
4. Authorized document access (assigned doctor)
5. Unauthorized document metadata IDOR (unassigned doctor -> 403 Forbidden)
6. Unauthorized document raw file download IDOR (unassigned doctor -> 403 Forbidden)
7. Unauthorized document page render IDOR (unassigned doctor -> 403 Forbidden)
8. Authorized consultation access (assigned doctor)
9. Unauthorized consultation access IDOR (unassigned doctor -> 403 Forbidden)
10. Memory proposal authorization IDOR (unassigned doctor -> 403 Forbidden)
11. Role boundaries (Nurse assigned to patient cannot approve clinical memory -> 403 Forbidden)
12. Audit log authorization (unassigned doctor -> 403 Forbidden; assigned doctor -> 200 OK)
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
from app.models.consultation import Consultation
from app.models.clinical_memory import ClinicalMemory
from app.models.audit_log import AuditLog
from app.utils.hashing import hash_password
from app.utils.tokens import create_access_token
from app.utils.ids import (
    user_id,
    patient_id,
    document_id,
    consultation_id,
    clinical_memory_id,
    audit_id,
)

client = TestClient(app)


def auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def auth_fixture():
    with get_db_context() as db:
        # Create test users
        uid_alice = user_id()
        alice = User(
            id=uid_alice,
            email="dr_alice_sec@clinsync.health",
            full_name="Dr. Alice Sec",
            role="doctor",
            specialty="Cardiology",
            hashed_password=hash_password("AliceSecure123!"),
            is_active=True,
        )

        uid_bob = user_id()
        bob = User(
            id=uid_bob,
            email="dr_bob_sec@clinsync.health",
            full_name="Dr. Bob Sec",
            role="doctor",
            specialty="Neurology",
            hashed_password=hash_password("BobSecure123!"),
            is_active=True,
        )

        uid_nancy = user_id()
        nancy = User(
            id=uid_nancy,
            email="nurse_nancy_sec@clinsync.health",
            full_name="Nurse Nancy Sec",
            role="nurse",
            specialty="General",
            hashed_password=hash_password("NancySecure123!"),
            is_active=True,
        )

        uid_adam = user_id()
        adam = User(
            id=uid_adam,
            email="admin_adam_sec@clinsync.health",
            full_name="Admin Adam Sec",
            role="admin",
            specialty="Administration",
            hashed_password=hash_password("AdamSecure123!"),
            is_active=True,
        )

        db.add_all([alice, bob, nancy, adam])
        db.flush()

        # Create isolated non-demo patient
        pid = patient_id()
        patient = Patient(
            id=pid,
            full_name="Confidential Patient X",
            age_years=45,
            sex="female",
            is_demo=False,
        )
        db.add(patient)
        db.flush()

        # Assign Alice to Patient X
        alice_access = PatientAccess(
            user_id=alice.id,
            patient_id=patient.id,
            access_level="primary_doctor",
        )
        db.add(alice_access)

        # Create Document for Patient X
        doc_x_id = document_id()
        doc_x = Document(
            id=doc_x_id,
            patient_id=patient.id,
            original_filename="confidential_cardiac_panel.pdf",
            stored_path="test_confidential.pdf",
            mime_type="application/pdf",
            file_size=1024,
            sha256="aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899",
            page_count=2,
            processing_status="completed",
        )
        db.add(doc_x)

        # Create Consultation for Patient X
        cns_x_id = consultation_id()
        cns_x = Consultation(
            id=cns_x_id,
            patient_id=patient.id,
            specialty="cardiology",
            status="draft",
        )
        db.add(cns_x)

        # Create Memory Proposal for Patient X
        mem_x_id = clinical_memory_id()
        mem_x = ClinicalMemory(
            id=mem_x_id,
            patient_id=patient.id,
            memory_type="allergy",
            content_json=json.dumps({"allergen": "Penicillin", "reaction": "Anaphylaxis"}),
            verified=False,
        )
        db.add(mem_x)

        # Create AuditLog for Patient X
        aud_x_id = audit_id()
        aud_x = AuditLog(
            id=aud_x_id,
            patient_id=patient.id,
            actor=alice.email,
            action="view_patient_chart",
            entity_type="patient",
            entity_id=patient.id,
        )
        db.add(aud_x)

        db.commit()

        tokens = {
            "alice": create_access_token(subject=alice.id, claims={"email": alice.email, "role": alice.role}),
            "bob": create_access_token(subject=bob.id, claims={"email": bob.email, "role": bob.role}),
            "nancy": create_access_token(subject=nancy.id, claims={"email": nancy.email, "role": nancy.role}),
            "adam": create_access_token(subject=adam.id, claims={"email": adam.email, "role": adam.role}),
        }

        data = {
            "patient_id": patient.id,
            "doc_id": doc_x.id,
            "consultation_id": cns_x.id,
            "memory_id": mem_x.id,
            "nurse_id": nancy.id,
            "tokens": tokens,
        }

    return data


class TestPatientIsolation:
    def test_authorized_patient_access(self, auth_fixture):
        pid = auth_fixture["patient_id"]
        token = auth_fixture["tokens"]["alice"]
        resp = client.get(f"/api/v1/patients/{pid}", headers=auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["data"]["full_name"] == "Confidential Patient X"

    def test_unauthorized_patient_access_idor(self, auth_fixture):
        pid = auth_fixture["patient_id"]
        token = auth_fixture["tokens"]["bob"]
        resp = client.get(f"/api/v1/patients/{pid}", headers=auth_header(token))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    def test_admin_bypass_patient_access(self, auth_fixture):
        pid = auth_fixture["patient_id"]
        token = auth_fixture["tokens"]["adam"]
        resp = client.get(f"/api/v1/patients/{pid}", headers=auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["data"]["full_name"] == "Confidential Patient X"


class TestDocumentAuthorizationIDOR:
    def test_authorized_document_access(self, auth_fixture):
        doc_id = auth_fixture["doc_id"]
        token = auth_fixture["tokens"]["alice"]
        resp = client.get(f"/api/v1/documents/{doc_id}", headers=auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["data"]["original_filename"] == "confidential_cardiac_panel.pdf"

    def test_unauthorized_document_metadata_idor(self, auth_fixture):
        doc_id = auth_fixture["doc_id"]
        token = auth_fixture["tokens"]["bob"]
        resp = client.get(f"/api/v1/documents/{doc_id}", headers=auth_header(token))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    def test_unauthorized_document_file_idor(self, auth_fixture):
        doc_id = auth_fixture["doc_id"]
        token = auth_fixture["tokens"]["bob"]
        # Raw file download must fail with 403 Forbidden
        resp = client.get(f"/api/v1/documents/{doc_id}/file", headers=auth_header(token))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    def test_unauthorized_document_page_idor(self, auth_fixture):
        doc_id = auth_fixture["doc_id"]
        token = auth_fixture["tokens"]["bob"]
        # Page render endpoint must fail with 403 Forbidden
        resp = client.get(f"/api/v1/documents/{doc_id}/pages/1", headers=auth_header(token))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"


class TestConsultationAuthorizationIDOR:
    def test_authorized_consultation_access(self, auth_fixture):
        cid = auth_fixture["consultation_id"]
        token = auth_fixture["tokens"]["alice"]
        resp = client.get(f"/api/v1/consultations/{cid}", headers=auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["data"]["patient_id"] == auth_fixture["patient_id"]

    def test_unauthorized_consultation_access_idor(self, auth_fixture):
        cid = auth_fixture["consultation_id"]
        token = auth_fixture["tokens"]["bob"]
        resp = client.get(f"/api/v1/consultations/{cid}", headers=auth_header(token))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"


class TestMemoryAndAuditAuthorizationIDOR:
    def test_unauthorized_memory_proposal_idor(self, auth_fixture):
        mem_id = auth_fixture["memory_id"]
        token = auth_fixture["tokens"]["bob"]
        # Doctor Bob has doctor role but NOT authorization for this patient
        resp = client.post(f"/api/v1/memories/{mem_id}/approve", headers=auth_header(token))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    def test_role_restriction_nurse_cannot_approve_memory(self, auth_fixture):
        mem_id = auth_fixture["memory_id"]
        # Even if nurse Nancy is given access to patient X:
        with get_db_context() as db:
            access = PatientAccess(
                user_id=auth_fixture["nurse_id"],
                patient_id=auth_fixture["patient_id"],
                access_level="care_team",
            )
            db.add(access)
            db.commit()

        token = auth_fixture["tokens"]["nancy"]
        resp = client.post(f"/api/v1/memories/{mem_id}/approve", headers=auth_header(token))
        assert resp.status_code == 403
        assert "not authorized" in resp.json()["error"]["message"].lower()

    def test_unauthorized_audit_access_idor(self, auth_fixture):
        pid = auth_fixture["patient_id"]
        token = auth_fixture["tokens"]["bob"]
        resp = client.get(f"/api/v1/patients/{pid}/audit", headers=auth_header(token))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    def test_authorized_audit_access(self, auth_fixture):
        pid = auth_fixture["patient_id"]
        token = auth_fixture["tokens"]["alice"]
        resp = client.get(f"/api/v1/patients/{pid}/audit", headers=auth_header(token))
        assert resp.status_code == 200
        assert isinstance(resp.json()["data"], list)
        assert len(resp.json()["data"]) >= 1
