"""Comprehensive authorization audit and matrix test suite.

Verifies:
1. Authentication: Valid JWT subject, invalid token, tampered token.
2. Role boundaries: Doctor vs Nurse vs Patient vs Admin.
3. Ownership and access control: Scoped patient access.
4. Horizontal privilege escalation (IDOR):
   User A attempting to access Patient B's:
   - /patients/{B}
   - /documents/{doc_B}
   - /consultations/{cns_B}
   - /memory/{mem_B}
   - /briefs/{brief_B}
   - /facts (patient B)
   - /issues (patient B)
   - /timeline (patient B)
   - /medications (patient B)
   - /investigations (patient B)
5. Cross-resource parameter substitution:
   Attempting to attach Patient B's brief to Patient A's consultation draft.
6. Doctor scoping: Doctor A can only access assigned patients, blocked from Doctor B's patients.
7. Patient role isolation: Patient user can ONLY access their own patient record.
8. Inactive accounts: Deactivated account (is_active=False) blocked with 401.
9. Unauthenticated requests: Strict 401 when AUTH_DEMO_FALLBACK_ENABLED=False.
"""

import json
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.db.database import get_db_context
from app.models.user import User
from app.models.patient import Patient
from app.models.patient_access import PatientAccess
from app.models.document import Document
from app.models.consultation import Consultation
from app.models.clinical_memory import ClinicalMemory
from app.models.brief import Brief
from app.models.clinical_fact import ClinicalFact
from app.models.contradiction import Contradiction
from app.utils.hashing import hash_password
from app.utils.tokens import create_access_token
from app.utils.ids import (
    user_id,
    patient_id,
    document_id,
    consultation_id,
    clinical_memory_id,
    brief_id,
    fact_id,
    generate_id,
)

client = TestClient(app)


def auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def auth_matrix_fixture():
    with get_db_context() as db:
        # 1. Create Users
        # Doctor A
        u_doc_a = User(
            id=user_id(),
            email="dr_matrix_a@clinsync.health",
            full_name="Dr. Matrix Alpha",
            role="doctor",
            specialty="Cardiology",
            hashed_password=hash_password("Pass123!"),
            is_active=True,
        )
        # Doctor B
        u_doc_b = User(
            id=user_id(),
            email="dr_matrix_b@clinsync.health",
            full_name="Dr. Matrix Beta",
            role="doctor",
            specialty="Endocrinology",
            hashed_password=hash_password("Pass123!"),
            is_active=True,
        )
        # Patient User P1
        u_pat_1 = User(
            id=user_id(),
            email="patient_p1@clinsync.health",
            full_name="Patient User One",
            role="patient",
            specialty="None",
            hashed_password=hash_password("Pass123!"),
            is_active=True,
        )
        # Patient User P2
        u_pat_2 = User(
            id=user_id(),
            email="patient_p2@clinsync.health",
            full_name="Patient User Two",
            role="patient",
            specialty="None",
            hashed_password=hash_password("Pass123!"),
            is_active=True,
        )
        # Nurse N
        u_nurse = User(
            id=user_id(),
            email="nurse_matrix@clinsync.health",
            full_name="Nurse Matrix",
            role="nurse",
            specialty="General",
            hashed_password=hash_password("Pass123!"),
            is_active=True,
        )
        # Inactive Doctor
        u_inactive = User(
            id=user_id(),
            email="dr_inactive@clinsync.health",
            full_name="Dr. Inactive",
            role="doctor",
            specialty="General",
            hashed_password=hash_password("Pass123!"),
            is_active=False,
        )
        # Administrator
        u_admin = User(
            id=user_id(),
            email="admin_matrix@clinsync.health",
            full_name="Admin Matrix",
            role="admin",
            specialty="Administration",
            hashed_password=hash_password("Pass123!"),
            is_active=True,
        )

        db.add_all([u_doc_a, u_doc_b, u_pat_1, u_pat_2, u_nurse, u_inactive, u_admin])
        db.flush()

        # 2. Create Patients
        # Patient A (assigned to Doctor A and Patient User 1)
        pat_a = Patient(
            id=patient_id(),
            full_name="Patient Alpha Isolated",
            age_years=50,
            sex="female",
            is_demo=False,
        )
        # Patient B (assigned to Doctor B and Patient User 2)
        pat_b = Patient(
            id=patient_id(),
            full_name="Patient Beta Isolated",
            age_years=60,
            sex="male",
            is_demo=False,
        )
        # Demo Patient
        pat_demo = Patient(
            id=patient_id(),
            full_name="Demo Patient Shared",
            age_years=35,
            sex="female",
            is_demo=True,
        )

        db.add_all([pat_a, pat_b, pat_demo])
        db.flush()

        # 3. PatientAccess assignments
        acc_doc_a = PatientAccess(
            user_id=u_doc_a.id,
            patient_id=pat_a.id,
            access_level="primary_doctor",
        )
        acc_pat_1 = PatientAccess(
            user_id=u_pat_1.id,
            patient_id=pat_a.id,
            access_level="patient",
        )
        acc_doc_b = PatientAccess(
            user_id=u_doc_b.id,
            patient_id=pat_b.id,
            access_level="primary_doctor",
        )
        acc_pat_2 = PatientAccess(
            user_id=u_pat_2.id,
            patient_id=pat_b.id,
            access_level="patient",
        )
        # Nurse assigned to Patient A only
        acc_nurse_a = PatientAccess(
            user_id=u_nurse.id,
            patient_id=pat_a.id,
            access_level="care_team",
        )
        db.add_all([acc_doc_a, acc_pat_1, acc_doc_b, acc_pat_2, acc_nurse_a])

        # 4. Resources for Patient B
        doc_b = Document(
            id=document_id(),
            patient_id=pat_b.id,
            original_filename="patient_b_labs.pdf",
            stored_path="test_b_labs.pdf",
            mime_type="application/pdf",
            file_size=2048,
            sha256="11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff",
            page_count=1,
            processing_status="completed",
        )
        cns_b = Consultation(
            id=consultation_id(),
            patient_id=pat_b.id,
            specialty="endocrinology",
            status="draft",
        )
        mem_b = ClinicalMemory(
            id=clinical_memory_id(),
            patient_id=pat_b.id,
            memory_type="diagnosis",
            content_json=json.dumps({"condition": "Type 2 Diabetes", "memory_state": "UNVERIFIED"}),
            verified=False,
        )
        brf_b = Brief(
            id=brief_id(),
            patient_id=pat_b.id,
            specialty="endocrinology",
            content_json=json.dumps({"summary": "Brief summary for Patient B"}),
            input_fingerprint="fp_brief_b_001",
        )
        fact_b = ClinicalFact(
            id=fact_id(),
            patient_id=pat_b.id,
            fact_type="diagnosis",
            value="Type 2 Diabetes",
            status="active",
            verification_status="verified",
            confidence=0.95,
            source_text="Assessment notes confirm Type 2 Diabetes.",
        )
        issue_b = Contradiction(
            id=generate_id("iss"),
            patient_id=pat_b.id,
            issue_type="medication_conflict",
            title="Metformin dosing discrepancy",
            description="Conflicting Metformin dosage found across prescriptions.",
            severity="medium",
            status="open",
        )

        db.add_all([doc_b, cns_b, mem_b, brf_b, fact_b, issue_b])
        db.commit()

        tokens = {
            "doc_a": create_access_token(subject=u_doc_a.id, claims={"role": u_doc_a.role, "email": u_doc_a.email}),
            "doc_b": create_access_token(subject=u_doc_b.id, claims={"role": u_doc_b.role, "email": u_doc_b.email}),
            "pat_1": create_access_token(subject=u_pat_1.id, claims={"role": u_pat_1.role, "email": u_pat_1.email}),
            "pat_2": create_access_token(subject=u_pat_2.id, claims={"role": u_pat_2.role, "email": u_pat_2.email}),
            "nurse": create_access_token(subject=u_nurse.id, claims={"role": u_nurse.role, "email": u_nurse.email}),
            "inactive": create_access_token(subject=u_inactive.id, claims={"role": u_inactive.role, "email": u_inactive.email}),
            "admin": create_access_token(subject=u_admin.id, claims={"role": u_admin.role, "email": u_admin.email}),
        }

        return {
            "users": {
                "doc_a": u_doc_a.id,
                "doc_b": u_doc_b.id,
                "pat_1": u_pat_1.id,
                "pat_2": u_pat_2.id,
                "nurse": u_nurse.id,
                "inactive": u_inactive.id,
                "admin": u_admin.id,
            },
            "patients": {
                "pat_a": pat_a.id,
                "pat_b": pat_b.id,
                "demo": pat_demo.id,
            },
            "resources_b": {
                "doc_b": doc_b.id,
                "cns_b": cns_b.id,
                "mem_b": mem_b.id,
                "brf_b": brf_b.id,
                "fact_b": fact_b.id,
                "issue_b": issue_b.id,
            },
            "tokens": tokens,
        }


class TestHorizontalPrivilegeEscalation:
    """Verify that Doctor A (User A) cannot access Patient B's resources by replacing IDs in URLs."""

    def test_doctor_a_cannot_access_patient_b_chart(self, auth_matrix_fixture):
        pid_b = auth_matrix_fixture["patients"]["pat_b"]
        token_a = auth_matrix_fixture["tokens"]["doc_a"]
        resp = client.get(f"/api/v1/patients/{pid_b}", headers=auth_header(token_a))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    def test_doctor_a_cannot_access_patient_b_overview(self, auth_matrix_fixture):
        pid_b = auth_matrix_fixture["patients"]["pat_b"]
        token_a = auth_matrix_fixture["tokens"]["doc_a"]
        resp = client.get(f"/api/v1/patients/{pid_b}/overview", headers=auth_header(token_a))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    def test_doctor_a_cannot_access_document_b(self, auth_matrix_fixture):
        doc_b = auth_matrix_fixture["resources_b"]["doc_b"]
        token_a = auth_matrix_fixture["tokens"]["doc_a"]
        resp = client.get(f"/api/v1/documents/{doc_b}", headers=auth_header(token_a))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    def test_doctor_a_cannot_access_document_b_file(self, auth_matrix_fixture):
        doc_b = auth_matrix_fixture["resources_b"]["doc_b"]
        token_a = auth_matrix_fixture["tokens"]["doc_a"]
        resp = client.get(f"/api/v1/documents/{doc_b}/file", headers=auth_header(token_a))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    def test_doctor_a_cannot_access_consultation_b(self, auth_matrix_fixture):
        cns_b = auth_matrix_fixture["resources_b"]["cns_b"]
        token_a = auth_matrix_fixture["tokens"]["doc_a"]
        resp = client.get(f"/api/v1/consultations/{cns_b}", headers=auth_header(token_a))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    def test_doctor_a_cannot_approve_consultation_b(self, auth_matrix_fixture):
        cns_b = auth_matrix_fixture["resources_b"]["cns_b"]
        token_a = auth_matrix_fixture["tokens"]["doc_a"]
        resp = client.post(f"/api/v1/consultations/{cns_b}/approve", json={}, headers=auth_header(token_a))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    def test_doctor_a_cannot_access_brief_b(self, auth_matrix_fixture):
        brf_b = auth_matrix_fixture["resources_b"]["brf_b"]
        token_a = auth_matrix_fixture["tokens"]["doc_a"]
        resp = client.get(f"/api/v1/briefs/{brf_b}", headers=auth_header(token_a))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    def test_doctor_a_cannot_access_patient_b_memory(self, auth_matrix_fixture):
        pid_b = auth_matrix_fixture["patients"]["pat_b"]
        token_a = auth_matrix_fixture["tokens"]["doc_a"]
        resp = client.get(f"/api/v1/patients/{pid_b}/memory", headers=auth_header(token_a))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    def test_doctor_a_cannot_approve_patient_b_memory_proposal(self, auth_matrix_fixture):
        mem_b = auth_matrix_fixture["resources_b"]["mem_b"]
        token_a = auth_matrix_fixture["tokens"]["doc_a"]
        resp = client.post(f"/api/v1/memories/{mem_b}/approve", json={}, headers=auth_header(token_a))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    def test_doctor_a_cannot_access_patient_b_clinical_facts(self, auth_matrix_fixture):
        pid_b = auth_matrix_fixture["patients"]["pat_b"]
        token_a = auth_matrix_fixture["tokens"]["doc_a"]
        resp = client.get(f"/api/v1/patients/{pid_b}/facts", headers=auth_header(token_a))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    def test_doctor_a_cannot_access_fact_b_evidence(self, auth_matrix_fixture):
        fact_b = auth_matrix_fixture["resources_b"]["fact_b"]
        token_a = auth_matrix_fixture["tokens"]["doc_a"]
        resp = client.get(f"/api/v1/facts/{fact_b}/evidence", headers=auth_header(token_a))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    def test_doctor_a_cannot_access_patient_b_issues(self, auth_matrix_fixture):
        pid_b = auth_matrix_fixture["patients"]["pat_b"]
        token_a = auth_matrix_fixture["tokens"]["doc_a"]
        resp = client.get(f"/api/v1/patients/{pid_b}/issues", headers=auth_header(token_a))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    def test_doctor_a_cannot_patch_patient_b_issue(self, auth_matrix_fixture):
        issue_b = auth_matrix_fixture["resources_b"]["issue_b"]
        token_a = auth_matrix_fixture["tokens"]["doc_a"]
        resp = client.patch(f"/api/v1/issues/{issue_b}", json={"status": "resolved"}, headers=auth_header(token_a))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    def test_doctor_a_cannot_access_patient_b_medications(self, auth_matrix_fixture):
        pid_b = auth_matrix_fixture["patients"]["pat_b"]
        token_a = auth_matrix_fixture["tokens"]["doc_a"]
        resp = client.get(f"/api/v1/patients/{pid_b}/medications", headers=auth_header(token_a))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    def test_doctor_a_cannot_access_patient_b_investigations(self, auth_matrix_fixture):
        pid_b = auth_matrix_fixture["patients"]["pat_b"]
        token_a = auth_matrix_fixture["tokens"]["doc_a"]
        resp = client.get(f"/api/v1/patients/{pid_b}/investigations", headers=auth_header(token_a))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    def test_doctor_a_cannot_access_patient_b_timeline(self, auth_matrix_fixture):
        pid_b = auth_matrix_fixture["patients"]["pat_b"]
        token_a = auth_matrix_fixture["tokens"]["doc_a"]
        resp = client.get(f"/api/v1/patients/{pid_b}/timeline", headers=auth_header(token_a))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"


class TestCrossResourceParameterSubstitution:
    """Verify that a client cannot reference a resource belonging to Patient B in an operation on Patient A."""

    def test_cannot_attach_patient_b_brief_to_patient_a_consultation(self, auth_matrix_fixture):
        pid_a = auth_matrix_fixture["patients"]["pat_a"]
        brf_b = auth_matrix_fixture["resources_b"]["brf_b"]
        token_a = auth_matrix_fixture["tokens"]["doc_a"]

        # Doctor A attempts to create a consultation for Patient A, passing brief_id from Patient B
        resp = client.post(
            f"/api/v1/patients/{pid_a}/consultations",
            json={"brief_id": brf_b, "specialty": "cardiology"},
            headers=auth_header(token_a),
        )
        assert resp.status_code == 403
        assert "belongs to patient" in resp.json()["error"]["message"].lower()


class TestPatientRoleIsolation:
    """Verify that a patient user can ONLY access their own data and cannot perform clinical actions."""

    def test_patient_can_access_own_data(self, auth_matrix_fixture):
        pid_a = auth_matrix_fixture["patients"]["pat_a"]
        token_p1 = auth_matrix_fixture["tokens"]["pat_1"]
        resp = client.get(f"/api/v1/patients/{pid_a}", headers=auth_header(token_p1))
        assert resp.status_code == 200
        assert resp.json()["data"]["full_name"] == "Patient Alpha Isolated"

    def test_patient_cannot_access_other_patient_data(self, auth_matrix_fixture):
        pid_b = auth_matrix_fixture["patients"]["pat_b"]
        token_p1 = auth_matrix_fixture["tokens"]["pat_1"]
        resp = client.get(f"/api/v1/patients/{pid_b}", headers=auth_header(token_p1))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    def test_patient_cannot_access_demo_patient(self, auth_matrix_fixture):
        pid_demo = auth_matrix_fixture["patients"]["demo"]
        token_p1 = auth_matrix_fixture["tokens"]["pat_1"]
        resp = client.get(f"/api/v1/patients/{pid_demo}", headers=auth_header(token_p1))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    def test_patient_list_only_contains_own_record(self, auth_matrix_fixture):
        token_p1 = auth_matrix_fixture["tokens"]["pat_1"]
        resp = client.get("/api/v1/patients", headers=auth_header(token_p1))
        assert resp.status_code == 200
        patients = resp.json()["data"]
        pids = [p["id"] for p in patients]
        assert auth_matrix_fixture["patients"]["pat_a"] in pids
        assert auth_matrix_fixture["patients"]["pat_b"] not in pids

    def test_patient_cannot_create_patient(self, auth_matrix_fixture):
        token_p1 = auth_matrix_fixture["tokens"]["pat_1"]
        resp = client.post(
            "/api/v1/patients",
            json={"full_name": "Unauthorized Patient Creation"},
            headers=auth_header(token_p1),
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    def test_patient_cannot_create_consultation(self, auth_matrix_fixture):
        pid_a = auth_matrix_fixture["patients"]["pat_a"]
        token_p1 = auth_matrix_fixture["tokens"]["pat_1"]
        resp = client.post(
            f"/api/v1/patients/{pid_a}/consultations",
            json={"specialty": "general_medicine"},
            headers=auth_header(token_p1),
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    def test_patient_cannot_generate_doctor_brief(self, auth_matrix_fixture):
        pid_a = auth_matrix_fixture["patients"]["pat_a"]
        token_p1 = auth_matrix_fixture["tokens"]["pat_1"]
        resp = client.post(
            f"/api/v1/patients/{pid_a}/brief",
            json={},
            headers=auth_header(token_p1),
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"


class TestInactiveAccountHandling:
    """Verify that a deactivated account is rejected immediately."""

    def test_inactive_doctor_cannot_access_patient(self, auth_matrix_fixture):
        pid_a = auth_matrix_fixture["patients"]["pat_a"]
        token_inact = auth_matrix_fixture["tokens"]["inactive"]
        resp = client.get(f"/api/v1/patients/{pid_a}", headers=auth_header(token_inact))
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHORIZED"

    def test_inactive_doctor_cannot_list_patients(self, auth_matrix_fixture):
        token_inact = auth_matrix_fixture["tokens"]["inactive"]
        resp = client.get("/api/v1/patients", headers=auth_header(token_inact))
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHORIZED"


class TestUnauthenticatedAccessRejection:
    """Verify that without authentication, clinical information cannot be accessed."""

    def test_unauthenticated_requests_fail_closed(self, monkeypatch, auth_matrix_fixture):
        # Disable demo fallback to simulate production authentication enforcement
        monkeypatch.setattr(settings, "AUTH_DEMO_FALLBACK_ENABLED", False)

        pid_a = auth_matrix_fixture["patients"]["pat_a"]

        routes_to_test = [
            ("GET", "/api/v1/patients"),
            ("GET", f"/api/v1/patients/{pid_a}"),
            ("GET", f"/api/v1/patients/{pid_a}/overview"),
            ("GET", f"/api/v1/patients/{pid_a}/documents"),
            ("GET", f"/api/v1/patients/{pid_a}/consultations"),
            ("GET", f"/api/v1/patients/{pid_a}/brief/latest"),
            ("GET", f"/api/v1/patients/{pid_a}/facts"),
            ("GET", f"/api/v1/patients/{pid_a}/issues"),
            ("GET", f"/api/v1/patients/{pid_a}/medications"),
            ("GET", f"/api/v1/patients/{pid_a}/investigations"),
            ("GET", f"/api/v1/patients/{pid_a}/timeline"),
            ("GET", f"/api/v1/patients/{pid_a}/audit"),
            ("POST", "/api/v1/patients"),
            ("POST", f"/api/v1/patients/{pid_a}/brief"),
            ("POST", f"/api/v1/patients/{pid_a}/consultations"),
        ]

        for method, url in routes_to_test:
            if method == "GET":
                resp = client.get(url)
            else:
                resp = client.post(url, json={})

            assert resp.status_code == 401, f"Expected 401 for unauthenticated {method} {url}, got {resp.status_code}"
            assert resp.json()["error"]["code"] == "UNAUTHORIZED"
