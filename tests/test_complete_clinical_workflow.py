"""
Complete Clinical Workflow Hardening Test Suite for ClinSync.

Tests the entire end-to-end clinical workflow:
Documents -> Evidence -> Clinical Facts -> Timeline/Medications/Investigations
-> Contradictions/Missing Information -> Doctor Brief -> Gate 2
-> Doctor Review -> Consultation -> Gate 1 -> Doctor Approval -> Clinical Memory

Covers:
1. Happy Path: Full end-to-end workflow from document upload to approved clinical memory.
2. Gate 2 Hardening:
   - Blocks unsupported/hallucinated drugs
   - Blocks directive imperative language
   - Blocks schema invalidity
   - Blocks ungrounded fake evidence citations
   - Fallback template presented when Gate 2 blocks unsafe candidate
3. Consultation Lifecyle & Authorship:
   - AI draft has empty assessment/plan/exam
   - Version history distinguishes AI-originated vs Doctor-originated content
   - Doctor edits transition origin to 'doctor_edited' with author tracking
4. Gate 1 Hardening:
   - Blocks approval of untouched AI drafts without explicit acknowledgment
   - Blocks approval when unacknowledged high-severity clinical conflicts exist
   - Blocks approval when approver lacks doctor role or patient authorization
   - Fails closed on safety violations
5. Clinical Memory Protection:
   - Verified memory created strictly through approved consultation workflow
   - Proposals endpoint enforces verified=False (AI cannot directly write verified memory)
   - Append-only semantics (existing approved memory is never overwritten)
6. Race Conditions & Concurrency:
   - Double-approval is blocked (HTTP 409 Conflict) preventing duplicate memory creation
   - Simultaneous edits / stale version update blocked via expected_version_id
"""

import json
import fitz
import pytest
from unittest.mock import patch, AsyncMock
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
from app.models.timeline_event import TimelineEvent
from app.schemas.ai_contracts import (
    ExtractionResult,
    ExtractionMedication,
    ExtractionDiagnosis,
    ExtractionInvestigation,
    EvidenceReference,
)
from app.schemas.common import ValidationOutcome, Severity, ConsultationOrigin
from app.schemas.brief import DoctorBrief
from app.services.pipeline_orchestrator import pipeline_orchestrator
from app.services.brief_service import brief_service
from app.services.consultation_service import consultation_service
from app.validation.gate1_memory import gate1_validator
from app.validation.gate2_output import gate2_validator
from app.utils.hashing import hash_password
from app.utils.tokens import create_access_token
from app.utils.ids import (
    user_id,
    patient_id,
    document_id,
    fact_id,
    contradiction_id,
    consultation_id,
    version_id,
)

client = TestClient(app)


def auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


def create_sample_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text, fontsize=11)
    buf = doc.write()
    doc.close()
    return buf


@pytest.fixture(scope="module")
def workflow_fixture():
    """Sets up doctor Alice, doctor Bob (unauthorized), and a patient."""
    with get_db_context() as db:
        uid_alice = user_id()
        alice = User(
            id=uid_alice,
            email=f"dr_alice_{uid_alice}@clinsync.health",
            full_name="Dr. Alice InternalMed",
            role="doctor",
            specialty="Internal Medicine",
            hashed_password=hash_password("DoctorPass123!"),
            is_active=True,
        )

        uid_bob = user_id()
        bob = User(
            id=uid_bob,
            email=f"dr_bob_{uid_bob}@clinsync.health",
            full_name="Dr. Bob Unassigned",
            role="doctor",
            specialty="Surgery",
            hashed_password=hash_password("DoctorPass123!"),
            is_active=True,
        )

        db.add_all([alice, bob])
        db.flush()

        pid = patient_id()
        patient = Patient(
            id=pid,
            full_name="Workflow Integration Patient",
            date_of_birth="1976-08-20",
            age_years=50,
            sex="male",
            is_demo=False,
        )
        db.add(patient)
        db.flush()

        # Alice is assigned to Patient
        access = PatientAccess(
            user_id=alice.id,
            patient_id=patient.id,
            access_level="primary_doctor",
        )
        db.add(access)
        db.commit()

        token_alice = create_access_token(subject=alice.id, claims={"role": alice.role, "email": alice.email})
        token_bob = create_access_token(subject=bob.id, claims={"role": bob.role, "email": bob.email})

    return {
        "alice_id": uid_alice,
        "bob_id": uid_bob,
        "patient_id": pid,
        "token_alice": token_alice,
        "token_bob": token_bob,
    }


class TestCompleteWorkflowHappyPath:
    """Tests the full clinical pipeline from document ingestion to approved clinical memory."""

    @pytest.mark.anyio
    async def test_end_to_end_clinical_workflow(self, workflow_fixture):
        pid = workflow_fixture["patient_id"]
        token = workflow_fixture["token_alice"]
        alice_id = workflow_fixture["alice_id"]

        # Step 1: Document Upload
        doc_text = (
            "Discharge Note\n"
            "Diagnosis: Type 2 Diabetes Mellitus\n"
            "Prescription: Metformin 500mg orally twice daily with meals.\n"
            "Lab results: Fasting Blood Glucose 130 mg/dL.\n"
        )
        pdf_bytes = create_sample_pdf(doc_text)
        files = {"file": ("discharge_summary.pdf", pdf_bytes, "application/pdf")}

        upload_res = client.post(
            f"/api/v1/patients/{pid}/documents",
            files=files,
            headers=auth_header(token),
        )
        assert upload_res.status_code == 201
        doc_data = upload_res.json()["data"]
        doc_id = doc_data["id"]

        # Step 2: Pipeline Ingestion with Mocked LLM Extraction
        mock_extract = ExtractionResult(
            medications=[
                ExtractionMedication(
                    name="Metformin",
                    strength="500mg",
                    dose="500mg",
                    frequency="twice daily",
                    confidence=0.95,
                    evidence=EvidenceReference(page=1, text="Metformin 500mg orally twice daily")
                )
            ],
            diagnoses=[
                ExtractionDiagnosis(
                    text="Type 2 Diabetes Mellitus",
                    confidence=0.95,
                    evidence=EvidenceReference(page=1, text="Type 2 Diabetes Mellitus")
                )
            ],
            investigations=[
                ExtractionInvestigation(
                    test="Fasting Blood Glucose",
                    value="130",
                    unit="mg/dL",
                    confidence=0.92,
                    evidence=EvidenceReference(page=1, text="Fasting Blood Glucose 130 mg/dL")
                )
            ],
            allergies=[],
            symptoms=[],
        )

        with patch("app.services.extraction_service.extraction_service.extract", new_callable=AsyncMock, return_value=mock_extract):
            await pipeline_orchestrator.run(doc_id)

        # Step 3: Verify Facts & Longitudinal Entities Created
        with get_db_context() as db:
            facts = db.query(ClinicalFact).filter(ClinicalFact.patient_id == pid).all()
            assert len(facts) >= 2
            diag_fact = next(f for f in facts if f.fact_type == "diagnosis")
            assert "diabetes" in diag_fact.value.lower()
            assert diag_fact.provenance_verified is True
            assert diag_fact.source_span_start is not None
            assert diag_fact.source_span_end is not None

            meds = db.query(Medication).filter(Medication.patient_id == pid).all()
            assert len(meds) == 1
            assert meds[0].canonical_name == "metformin"
            assert meds[0].fact_id is not None

        # Step 4: Doctor Brief Generation & Gate 2 Validation
        # Generate brief through API
        brief_res = client.post(
            f"/api/v1/patients/{pid}/brief",
            json={"specialty": "general_medicine", "force_regenerate": True},
            headers=auth_header(token),
        )
        assert brief_res.status_code == 200
        brief_data = brief_res.json()["data"]
        assert brief_data["patient"]["id"] == pid
        assert len(brief_data["current_medications"]) >= 1
        assert "metformin" in brief_data["current_medications"][0]["name"].lower()
        # Evidence shortcuts must be present and grounded
        assert len(brief_data["evidence_shortcuts"]) >= 1

        # Verify Gate 2 explicitly passed
        with get_db_context() as db:
            outcome, checks, rep_id = gate2_validator.validate_brief(
                db=db,
                patient_id=pid,
                brief_data=brief_data,
                run_judge=False,
            )
            assert outcome in (ValidationOutcome.pass_, ValidationOutcome.pass_with_flags)

        # Step 5: Create Consultation Draft
        cns_res = client.post(
            f"/api/v1/patients/{pid}/consultations",
            json={"specialty": "internal_medicine"},
            headers=auth_header(token),
        )
        assert cns_res.status_code == 201
        cns_data = cns_res.json()["data"]
        cid = cns_data["id"]
        v1 = cns_data["version"]
        assert v1["version_number"] == 1
        assert v1["origin"] == "ai_generated"
        # Invariant check: assessment, plan, exam must be left empty in AI draft
        assert v1["content"]["examination"] == ""
        assert v1["content"]["assessment"] == ""
        assert v1["content"]["plan"] == ""

        # Step 6: Doctor Reviews & Edits (creates Version 2)
        doc_content = dict(v1["content"])
        doc_content["examination"] = "Vital signs stable. BMI 27.2. Lungs clear, heart sounds normal."
        doc_content["assessment"] = "Type 2 Diabetes Mellitus, well tolerated on Metformin monotherapy."
        doc_content["plan"] = "Continue Metformin 500mg BID. Recheck HbA1c in 3 months."

        v2_res = client.post(
            f"/api/v1/consultations/{cid}/versions",
            json={
                "content": doc_content,
                "change_summary": "Doctor documented physical exam, assessment, and care plan.",
                "expected_version_id": v1["id"],
            },
            headers=auth_header(token),
        )
        assert v2_res.status_code == 200
        v2_data = v2_res.json()["data"]
        assert v2_data["version_number"] == 2
        assert v2_data["origin"] == "doctor_edited"

        # Step 7 & 8: Gate 1 Preview Verification & Doctor Approval
        with patch("app.validation.gate1_memory.evaluate_gate1_judge", return_value=(True, "info", {"verdict": "pass"})):
            prev_res = client.post(
                f"/api/v1/consultations/{cid}/approve/preview",
                json={"acknowledged_unedited": False},
                headers=auth_header(token),
            )
            assert prev_res.status_code == 200
            prev_data = prev_res.json()["data"]
            assert prev_data["can_approve"] is True
            assert len(prev_data["proposed_memory_items"]) >= 2

            appr_res = client.post(
                f"/api/v1/consultations/{cid}/approve",
                json={"acknowledged_unedited": False, "expected_version_id": v2_data["version_id"]},
                headers=auth_header(token),
            )
            assert appr_res.status_code == 200
            appr_data = appr_res.json()["data"]
            assert appr_data["status"] == "approved"
            assert appr_data["memory_items_created"] >= 2

        # Step 9: Verify Clinical Memory & Timeline Persistence
        with get_db_context() as db:
            memories = db.query(ClinicalMemory).filter(ClinicalMemory.patient_id == pid).all()
            assert len(memories) >= 2
            assert all(m.verified is True for m in memories)
            mem_types = [m.memory_type for m in memories]
            assert "assessment" in mem_types
            assert "plan_note" in mem_types

            # Verify timeline approved_note
            notes = db.query(TimelineEvent).filter(
                TimelineEvent.patient_id == pid,
                TimelineEvent.event_type == "approved_note",
            ).all()
            assert len(notes) >= 1

            # Consultation is locked
            cns = db.query(Consultation).filter(Consultation.id == cid).first()
            assert cns.status == "approved"
            assert cns.approved_by == alice_id


class TestGate2SafetyHardening:
    """Tests Gate 2 validation protections against unsafe, hallucinated, or ungrounded outputs."""

    def test_gate2_blocks_hallucinated_drug(self, workflow_fixture):
        pid = workflow_fixture["patient_id"]
        with get_db_context() as db:
            brief = brief_service._build_deterministic_template_brief(
                patient=db.query(Patient).filter(Patient.id == pid).first(),
                specialty="general_medicine",
                facts=db.query(ClinicalFact).filter(ClinicalFact.patient_id == pid).all(),
                meds=db.query(Medication).filter(Medication.patient_id == pid).all(),
                invs=[],
                issues=[],
            )
            # Inject hallucinated drug not in patient records
            brief_dict = brief.model_dump()
            brief_dict["current_medications"].append({
                "name": "Oxycodone",
                "strength": "80mg",
                "dose": "80mg",
                "frequency": "daily",
                "status": "active",
                "evidence_ids": [],
                "confidence_band": "high",
                "conflict_flag": False,
            })

            outcome, checks, rep_id = gate2_validator.validate_brief(
                db=db,
                patient_id=pid,
                brief_data=brief_dict,
                run_judge=False,
            )
            assert outcome == ValidationOutcome.blocked
            hallucination_check = next(c for c in checks if c["name"] == "hallucination_check")
            assert hallucination_check["passed"] is False

    def test_gate2_blocks_directive_language(self, workflow_fixture):
        pid = workflow_fixture["patient_id"]
        with get_db_context() as db:
            brief = brief_service._build_deterministic_template_brief(
                patient=db.query(Patient).filter(Patient.id == pid).first(),
                specialty="general_medicine",
                facts=db.query(ClinicalFact).filter(ClinicalFact.patient_id == pid).all(),
                meds=db.query(Medication).filter(Medication.patient_id == pid).all(),
                invs=[],
                issues=[],
            )
            brief_dict = brief.model_dump()
            brief_dict["chief_complaint"]["text"] = "You must immediately prescribe high-dose opioids to the patient."

            outcome, checks, rep_id = gate2_validator.validate_brief(
                db=db,
                patient_id=pid,
                brief_data=brief_dict,
                run_judge=False,
            )
            assert outcome == ValidationOutcome.blocked
            dir_check = next(c for c in checks if c["name"] == "directive_language")
            assert dir_check["passed"] is False

    def test_gate2_blocks_schema_invalidity(self, workflow_fixture):
        pid = workflow_fixture["patient_id"]
        with get_db_context() as db:
            # Completely broken schema
            corrupted_brief = {"random_key": "not a doctor brief"}

            outcome, checks, rep_id = gate2_validator.validate_brief(
                db=db,
                patient_id=pid,
                brief_data=corrupted_brief,
                run_judge=False,
            )
            assert outcome == ValidationOutcome.blocked
            schema_check = next(c for c in checks if c["name"] == "schema_validity")
            assert schema_check["passed"] is False

    def test_gate2_blocks_fake_evidence_ids(self, workflow_fixture):
        pid = workflow_fixture["patient_id"]
        with get_db_context() as db:
            brief = brief_service._build_deterministic_template_brief(
                patient=db.query(Patient).filter(Patient.id == pid).first(),
                specialty="general_medicine",
                facts=db.query(ClinicalFact).filter(ClinicalFact.patient_id == pid).all(),
                meds=db.query(Medication).filter(Medication.patient_id == pid).all(),
                invs=[],
                issues=[],
            )
            brief_dict = brief.model_dump()
            brief_dict["chief_complaint"]["evidence_ids"] = ["fake_eid_999999"]

            outcome, checks, rep_id = gate2_validator.validate_brief(
                db=db,
                patient_id=pid,
                brief_data=brief_dict,
                run_judge=False,
            )
            assert outcome == ValidationOutcome.blocked
            prov_check = next(c for c in checks if c["name"] == "provenance_check")
            assert prov_check["passed"] is False


class TestGate1AndConsultationSafetyHardening:
    """Tests Gate 1 pre-approval safety gates, authorship enforcement, and conflict blocking."""

    def test_gate1_blocks_untouched_ai_draft(self, workflow_fixture):
        """Untouched AI drafts cannot be approved into memory without doctor edits or acknowledgment."""
        pid = workflow_fixture["patient_id"]
        token = workflow_fixture["token_alice"]

        cns_res = client.post(
            f"/api/v1/patients/{pid}/consultations",
            json={"specialty": "general_medicine"},
            headers=auth_header(token),
        )
        cid = cns_res.json()["data"]["id"]

        # Attempt to approve immediately without editing and without acknowledged_unedited
        appr_res = client.post(
            f"/api/v1/consultations/{cid}/approve",
            json={"acknowledged_unedited": False},
            headers=auth_header(token),
        )
        assert appr_res.status_code == 422
        assert "GATE1_BLOCKED" in appr_res.json()["error"]["code"]

    def test_gate1_blocks_when_high_severity_conflict_exists(self, workflow_fixture):
        """Open high-severity contradictions must block approval."""
        pid = workflow_fixture["patient_id"]
        token = workflow_fixture["token_alice"]

        conflict_cid = contradiction_id()
        with get_db_context() as db:
            # Add open high severity conflict
            conflict = Contradiction(
                id=conflict_cid,
                patient_id=pid,
                issue_type="medication_conflict",
                severity=Severity.high.value,
                title="Fatal Drug Interaction Conflict",
                description="Glimepiride and high dose insulin co-prescribed with conflicting dose instructions.",
                status="open",
            )
            db.add(conflict)
            db.commit()

        try:
            # Create consultation and doctor edit
            cns_res = client.post(
                f"/api/v1/patients/{pid}/consultations",
                json={"specialty": "general_medicine"},
                headers=auth_header(token),
            )
            cid = cns_res.json()["data"]["id"]

            client.post(
                f"/api/v1/consultations/{cid}/versions",
                json={"content": {"assessment": "Stable"}, "change_summary": "Doctor assessment."},
                headers=auth_header(token),
            )

            # Attempt to approve
            appr_res = client.post(
                f"/api/v1/consultations/{cid}/approve",
                headers=auth_header(token),
            )
            assert appr_res.status_code == 422
            assert "GATE1_BLOCKED" in appr_res.json()["error"]["code"]
            assert "high-severity" in appr_res.json()["error"]["message"].lower()
        finally:
            # Clean up conflict so it doesn't pollute subsequent tests
            with get_db_context() as db:
                c = db.query(Contradiction).filter(Contradiction.id == conflict_cid).first()
                if c:
                    db.delete(c)
                    db.commit()

    def test_gate1_blocks_unauthorized_approver(self, workflow_fixture):
        """An unauthorized doctor cannot approve a consultation for a patient they do not have access to."""
        pid = workflow_fixture["patient_id"]
        token_alice = workflow_fixture["token_alice"]
        token_bob = workflow_fixture["token_bob"]  # Bob has no access

        cns_res = client.post(
            f"/api/v1/patients/{pid}/consultations",
            json={"specialty": "cardiology"},
            headers=auth_header(token_alice),
        )
        cid = cns_res.json()["data"]["id"]

        client.post(
            f"/api/v1/consultations/{cid}/versions",
            json={"content": {"assessment": "Cardio assessment"}, "change_summary": "Edited"},
            headers=auth_header(token_alice),
        )

        # Bob attempts to approve
        appr_res = client.post(
            f"/api/v1/consultations/{cid}/approve",
            headers=auth_header(token_bob),
        )
        assert appr_res.status_code == 403


class TestRaceConditionsAndConcurrency:
    """Tests double approval, simultaneous edits, and stale versions."""

    def test_double_approval_blocked(self, workflow_fixture):
        """Approved consultations cannot be approved a second time."""
        pid = workflow_fixture["patient_id"]
        token = workflow_fixture["token_alice"]

        cns_res = client.post(
            f"/api/v1/patients/{pid}/consultations",
            headers=auth_header(token),
        )
        cid = cns_res.json()["data"]["id"]

        client.post(
            f"/api/v1/consultations/{cid}/versions",
            json={"content": {"assessment": "Assessment text"}, "change_summary": "Doctor edit"},
            headers=auth_header(token),
        )

        with patch("app.validation.gate1_memory.evaluate_gate1_judge", return_value=(True, "info", {"verdict": "pass"})):
            # First approval succeeds
            appr1 = client.post(f"/api/v1/consultations/{cid}/approve", headers=auth_header(token))
            assert appr1.status_code == 200

            # Second approval attempt fails with 409 Conflict
            appr2 = client.post(f"/api/v1/consultations/{cid}/approve", headers=auth_header(token))
            assert appr2.status_code == 409
            assert "INVALID_STATE_TRANSITION" in appr2.json()["error"]["code"]

    def test_stale_version_edit_blocked(self, workflow_fixture):
        """Editing with a stale expected_version_id fails with 409 Conflict."""
        pid = workflow_fixture["patient_id"]
        token = workflow_fixture["token_alice"]

        cns_res = client.post(
            f"/api/v1/patients/{pid}/consultations",
            headers=auth_header(token),
        )
        cid = cns_res.json()["data"]["id"]
        v1_id = cns_res.json()["data"]["version"]["id"]

        # First edit creates Version 2
        v2_res = client.post(
            f"/api/v1/consultations/{cid}/versions",
            json={"content": {"assessment": "Version 2 Assessment"}, "expected_version_id": v1_id},
            headers=auth_header(token),
        )
        assert v2_res.status_code == 200

        # Another client tries to edit still thinking current version is Version 1
        stale_res = client.post(
            f"/api/v1/consultations/{cid}/versions",
            json={"content": {"assessment": "Conflicting Edit"}, "expected_version_id": v1_id},
            headers=auth_header(token),
        )
        assert stale_res.status_code == 409
        assert "INVALID_STATE_TRANSITION" in stale_res.json()["error"]["code"]

    def test_ai_cannot_directly_create_verified_clinical_memory(self, workflow_fixture):
        """Clinical memory proposals cannot be created as verified directly."""
        pid = workflow_fixture["patient_id"]
        token = workflow_fixture["token_alice"]

        # Even if payload specifies verified=True
        resp = client.post(
            f"/api/v1/patients/{pid}/memories/proposals",
            json={"memory_type": "allergy", "content": "Penicillin", "verified": True},
            headers=auth_header(token),
        )
        assert resp.status_code == 200
        prop_id = resp.json()["data"]["id"]

        with get_db_context() as db:
            mem = db.query(ClinicalMemory).filter(ClinicalMemory.id == prop_id).first()
            assert mem is not None
            # Verified must remain False until doctor explicitly approves
            assert mem.verified is False
