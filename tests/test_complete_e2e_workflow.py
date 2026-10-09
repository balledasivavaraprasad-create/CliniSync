"""
End-to-End Integration Test: Complete ClinSync Clinical Workflow.

Scenario:
A patient has:
1. Previous prescription: Metformin 500 mg BD (dated 2026-01-10).
2. Previous lab report: HbA1c 8.4 % (dated 2026-01-15).
3. New lab report: HbA1c 7.8 % (dated 2026-04-18).
4. Current symptom input: Polyuria and persistent fatigue.
5. A medication discrepancy between two documents: Metformin 500 mg BD vs 1000 mg BD.

Executes:
PATIENT CREATION
    ↓
DOCUMENT UPLOAD
    ↓
DOCUMENT PROCESSING
    ↓
TEXT/OCR EXTRACTION
    ↓
CLINICAL ENTITY EXTRACTION
    ↓
NORMALIZATION
    ↓
EVIDENCE VERIFICATION
    ↓
TIMELINE CREATION
    ↓
MEDICATION RECONCILIATION
    ↓
LAB TREND DETECTION
    ↓
CONTRADICTION DETECTION
    ↓
MISSING INFORMATION DETECTION
    ↓
DOCTOR BRIEF GENERATION
    ↓
DOCTOR REVIEW
    ↓
DOCTOR EDIT
    ↓
VALIDATION
    ↓
APPROVAL
    ↓
CLINICAL MEMORY UPDATE
    ↓
SECOND CONSULTATION
    ↓
PREVIOUS APPROVED MEMORY RETRIEVED

Asserts:
- no fabricated clinical values exist
- every important fact has provenance
- conflicting information remains flagged
- lab changes are classified as trends rather than contradictions
- doctor approval is required
- clinical memory contains only approved/verified information
- historical information is preserved
- retrying processing does not create duplicates
- unauthorized users cannot access the patient
- LLM failure still produces a deterministic safe fallback
- the fallback clearly marks unavailable information
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import fitz
import pytest
from fastapi.testclient import TestClient

from app.db.database import get_db_context
from app.main import app
from app.models.clinical_fact import ClinicalFact
from app.models.clinical_memory import ClinicalMemory
from app.models.consultation import Consultation, ConsultationVersion
from app.models.contradiction import Contradiction
from app.models.document import Document
from app.models.investigation import Investigation
from app.models.medication import Medication
from app.models.patient import Patient
from app.models.patient_access import PatientAccess
from app.models.timeline_event import TimelineEvent
from app.models.user import User
from app.schemas.ai_contracts import (
    DocClassification,
    EvidenceReference,
    ExtractionDiagnosis,
    ExtractionGenericItem,
    ExtractionInvestigation,
    ExtractionMedication,
    ExtractionResult,
)
from app.schemas.common import ConsultationOrigin, FactType, Severity
from app.services.brief_service import brief_service
from app.services.difference_evaluator import DifferenceClassification, difference_evaluator
from app.services.pipeline_orchestrator import pipeline_orchestrator
from app.utils.hashing import hash_password
from app.utils.ids import patient_id, user_id
from app.utils.tokens import create_access_token

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
def e2e_fixture():
    """Sets up doctor Alice (authorized), doctor Bob (unauthorized), and an E2E patient."""
    with get_db_context() as db:
        uid_alice = user_id()
        alice = User(
            id=uid_alice,
            email=f"dr_alice_e2e_{uid_alice}@clinsync.health",
            full_name="Dr. Alice InternalMed",
            role="doctor",
            specialty="Internal Medicine",
            hashed_password=hash_password("DoctorPass123!"),
            is_active=True,
        )

        uid_bob = user_id()
        bob = User(
            id=uid_bob,
            email=f"dr_bob_e2e_{uid_bob}@clinsync.health",
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
            full_name="E2E Integration Patient",
            date_of_birth="1974-05-12",
            age_years=52,
            sex="male",
            is_demo=False,
        )
        db.add(patient)
        db.flush()

        # Alice is assigned primary doctor access
        access = PatientAccess(
            user_id=alice.id,
            patient_id=patient.id,
            access_level="primary_doctor",
        )
        db.add(access)
        db.commit()

        token_alice = create_access_token(
            subject=alice.id, claims={"role": alice.role, "email": alice.email}
        )
        token_bob = create_access_token(
            subject=bob.id, claims={"role": bob.role, "email": bob.email}
        )

    return {
        "alice_id": uid_alice,
        "bob_id": uid_bob,
        "patient_id": pid,
        "token_alice": token_alice,
        "token_bob": token_bob,
    }


class TestCompleteE2EWorkflow:
    @pytest.mark.anyio
    async def test_complete_clinsync_workflow_scenario(self, e2e_fixture):
        pid = e2e_fixture["patient_id"]
        token_alice = e2e_fixture["token_alice"]
        token_bob = e2e_fixture["token_bob"]
        alice_id = e2e_fixture["alice_id"]

        # =========================================================================
        # 1. SECURITY & AUTHORIZATION CHECK (Unauthorized users cannot access)
        # =========================================================================
        unauth_overview = client.get(
            f"/api/v1/patients/{pid}/overview", headers=auth_header(token_bob)
        )
        assert unauth_overview.status_code == 403, "Doctor Bob must not access unassigned patient"

        unauth_memory = client.get(
            f"/api/v1/patients/{pid}/memory", headers=auth_header(token_bob)
        )
        assert unauth_memory.status_code == 403, "Doctor Bob must not access patient memory"

        # =========================================================================
        # 2. DOCUMENT UPLOAD (4 documents representing the scenario)
        # =========================================================================
        # Document 1: Previous prescription (Jan 10, 2026) -> Metformin 500 mg BD
        doc1_text = (
            "PRESCRIPTION RECORD\n"
            "Date: 2026-01-10\n"
            "Patient: E2E Integration Patient (Age: 52)\n"
            "Diagnosis: Type 2 Diabetes Mellitus\n"
            "Rx: Tab. Metformin 500 mg orally twice daily (BD) with meals.\n"
        )
        pdf1 = create_sample_pdf(doc1_text)
        res1 = client.post(
            f"/api/v1/patients/{pid}/documents",
            files={"file": ("doc1_rx_jan2026.pdf", pdf1, "application/pdf")},
            data={"document_type_hint": "prescription", "document_date": "2026-01-10"},
            headers=auth_header(token_alice),
        )
        assert res1.status_code == 201
        doc1_id = res1.json()["data"]["id"]

        # Document 2: Previous lab report (Jan 15, 2026) -> HbA1c 8.4 %
        doc2_text = (
            "DIAGNOSTIC CLINICAL LABORATORY REPORT\n"
            "Date: 2026-01-15\n"
            "Patient: E2E Integration Patient (Age: 52)\n"
            "Test: HbA1c\n"
            "Result: 8.4 %\n"
            "Reference Range: 4.0 - 5.6 %\n"
            "Status: High\n"
        )
        pdf2 = create_sample_pdf(doc2_text)
        res2 = client.post(
            f"/api/v1/patients/{pid}/documents",
            files={"file": ("doc2_lab_jan2026.pdf", pdf2, "application/pdf")},
            data={"document_type_hint": "lab_report", "document_date": "2026-01-15"},
            headers=auth_header(token_alice),
        )
        assert res2.status_code == 201
        doc2_id = res2.json()["data"]["id"]

        # Document 3: New lab report (Apr 18, 2026) -> HbA1c 7.8 % (improving trend)
        doc3_text = (
            "DIAGNOSTIC CLINICAL LABORATORY REPORT\n"
            "Date: 2026-04-18\n"
            "Patient: E2E Integration Patient (Age: 52)\n"
            "Test: HbA1c\n"
            "Result: 7.8 %\n"
            "Reference Range: 4.0 - 5.6 %\n"
            "Status: High\n"
            "Observation: Sequential glycemic improvement from 8.4 %\n"
        )
        pdf3 = create_sample_pdf(doc3_text)
        res3 = client.post(
            f"/api/v1/patients/{pid}/documents",
            files={"file": ("doc3_lab_apr2026.pdf", pdf3, "application/pdf")},
            data={"document_type_hint": "lab_report", "document_date": "2026-04-18"},
            headers=auth_header(token_alice),
        )
        assert res3.status_code == 201
        doc3_id = res3.json()["data"]["id"]

        # Document 4: Second prescription with current symptom input & conflicting dose (Jan 10, 2026) -> Metformin 1000 mg BD
        doc4_text = (
            "OUTPATIENT CONSULTATION & PRESCRIPTION VOUCHER\n"
            "Date: 2026-01-10\n"
            "Patient: E2E Integration Patient (Age: 52)\n"
            "Symptoms: Polyuria and persistent fatigue for the past 2 weeks.\n"
            "Rx: Tab. Metformin 1000 mg orally twice daily (BD) with meals.\n"
        )
        pdf4 = create_sample_pdf(doc4_text)
        res4 = client.post(
            f"/api/v1/patients/{pid}/documents",
            files={"file": ("doc4_rx_discrepant_jan2026.pdf", pdf4, "application/pdf")},
            data={"document_type_hint": "prescription", "document_date": "2026-01-10"},
            headers=auth_header(token_alice),
        )
        assert res4.status_code == 201
        doc4_id = res4.json()["data"]["id"]

        # =========================================================================
        # 3. DOCUMENT PROCESSING (OCR, ENTITY EXTRACTION, NORMALIZATION, PROVENANCE)
        # =========================================================================
        async def mock_extract_dispatcher(pages, doc_type):
            text = "\n".join(p["text"] for p in pages)
            if "500 mg" in text:
                return ExtractionResult(
                    medications=[
                        ExtractionMedication(
                            name="Metformin",
                            strength="500 mg",
                            dose="500 mg",
                            frequency="twice daily (BD)",
                            confidence=0.96,
                            evidence=EvidenceReference(
                                page=1,
                                text="Tab. Metformin 500 mg orally twice daily (BD) with meals.",
                            ),
                        )
                    ],
                    diagnoses=[
                        ExtractionDiagnosis(
                            text="Type 2 Diabetes Mellitus",
                            date="2026-01-10",
                            confidence=0.95,
                            evidence=EvidenceReference(
                                page=1, text="Diagnosis: Type 2 Diabetes Mellitus"
                            ),
                        )
                    ],
                    investigations=[],
                    symptoms=[],
                    allergies=[],
                )
            elif "2026-01-15" in text:  # Doc 2 (Jan 15): HbA1c 8.4%
                return ExtractionResult(
                    medications=[],
                    diagnoses=[],
                    investigations=[
                        ExtractionInvestigation(
                            test="HbA1c",
                            value="8.4",
                            unit="%",
                            flag="high",
                            reference_range="4.0 - 5.6 %",
                            date="2026-01-15",
                            confidence=0.95,
                            evidence=EvidenceReference(page=1, text="Test: HbA1c\nResult: 8.4 %"),
                        )
                    ],
                    symptoms=[],
                    allergies=[],
                )
            elif "2026-04-18" in text:  # Doc 3 (Apr 18): HbA1c 7.8%
                return ExtractionResult(
                    medications=[],
                    diagnoses=[],
                    investigations=[
                        ExtractionInvestigation(
                            test="HbA1c",
                            value="7.8",
                            unit="%",
                            flag="high",
                            reference_range="4.0 - 5.6 %",
                            date="2026-04-18",
                            confidence=0.96,
                            evidence=EvidenceReference(page=1, text="Test: HbA1c\nResult: 7.8 %"),
                        )
                    ],
                    symptoms=[],
                    allergies=[],
                )
            else:  # Doc 4: discrepant 1000 mg + symptom input
                return ExtractionResult(
                    medications=[
                        ExtractionMedication(
                            name="Metformin",
                            strength="1000 mg",
                            dose="1000 mg",
                            frequency="twice daily (BD)",
                            confidence=0.95,
                            evidence=EvidenceReference(
                                page=1,
                                text="Tab. Metformin 1000 mg orally twice daily (BD) with meals.",
                            ),
                        )
                    ],
                    diagnoses=[],
                    investigations=[],
                    symptoms=[
                        ExtractionGenericItem(
                            text="Polyuria and persistent fatigue",
                            confidence=0.92,
                            evidence=EvidenceReference(
                                page=1,
                                text="Symptoms: Polyuria and persistent fatigue for the past 2 weeks.",
                            ),
                        )
                    ],
                    allergies=[],
                )

        with patch(
            "app.services.extraction_service.extraction_service.extract",
            side_effect=mock_extract_dispatcher,
        ):
            await pipeline_orchestrator.run(doc1_id)
            await pipeline_orchestrator.run(doc2_id)
            await pipeline_orchestrator.run(doc3_id)
            await pipeline_orchestrator.run(doc4_id)

        # =========================================================================
        # 4. ASSERTION: IDEMPOTENCY / RETRY PROCESSING CREATES NO DUPLICATES
        # =========================================================================
        with get_db_context() as db:
            facts_before_retry = (
                db.query(ClinicalFact).filter(ClinicalFact.document_id == doc1_id).count()
            )
            meds_before_retry = (
                db.query(Medication).filter(Medication.source_document_id == doc1_id).count()
            )
            events_before_retry = (
                db.query(TimelineEvent).filter(TimelineEvent.source_document_id == doc1_id).count()
            )

        with patch(
            "app.services.extraction_service.extraction_service.extract",
            side_effect=mock_extract_dispatcher,
        ):
            # Retrying document processing on doc1
            await pipeline_orchestrator.run(doc1_id, is_reprocess=True)

        with get_db_context() as db:
            facts_after_retry = (
                db.query(ClinicalFact).filter(ClinicalFact.document_id == doc1_id).count()
            )
            meds_after_retry = (
                db.query(Medication).filter(Medication.source_document_id == doc1_id).count()
            )
            events_after_retry = (
                db.query(TimelineEvent).filter(TimelineEvent.source_document_id == doc1_id).count()
            )

            assert facts_after_retry == facts_before_retry, (
                "Retrying processing must not create duplicate clinical facts"
            )
            assert meds_after_retry == meds_before_retry, (
                "Retrying processing must not create duplicate medications"
            )
            assert events_after_retry == events_before_retry, (
                "Retrying processing must not create duplicate timeline events"
            )

        # =========================================================================
        # 5. ASSERTION: NO FABRICATION & EVERY IMPORTANT FACT HAS PROVENANCE
        # =========================================================================
        with get_db_context() as db:
            all_facts = db.query(ClinicalFact).filter(ClinicalFact.patient_id == pid).all()
            assert len(all_facts) >= 5, "All facts from 4 documents must be extracted"

            for fact in all_facts:
                # Provenance assertions
                assert fact.provenance_verified is True, (
                    f"Fact {fact.id} ({fact.value}) must be provenance verified"
                )
                assert fact.source_text is not None and len(fact.source_text) > 0, (
                    f"Fact {fact.id} must retain exact source snippet"
                )
                assert fact.source_span_start is not None and fact.source_span_end is not None, (
                    f"Fact {fact.id} must record grounded character span offsets"
                )
                assert fact.source_span_end > fact.source_span_start, (
                    f"Fact {fact.id} span offsets must be valid"
                )

                # No fabricated clinical values
                if fact.fact_type == FactType.medication.value:
                    assert "metformin" in fact.value.lower(), (
                        f"Unexpected ungrounded medication value {fact.value}"
                    )
                elif fact.fact_type == FactType.investigation.value:
                    assert "8.4" in fact.value or "7.8" in fact.value, (
                        f"Unexpected ungrounded investigation value {fact.value}"
                    )
                elif fact.fact_type == FactType.symptom.value:
                    assert "polyuria" in fact.value.lower(), (
                        f"Unexpected ungrounded symptom value {fact.value}"
                    )

        # =========================================================================
        # 6. ASSERTION: LAB CHANGES ARE CLASSIFIED AS TRENDS, NOT CONTRADICTIONS
        # =========================================================================
        with get_db_context() as db:
            invs = (
                db.query(Investigation)
                .filter(Investigation.patient_id == pid)
                .order_by(Investigation.observed_date.asc())
                .all()
            )
            assert len(invs) == 2, "Must have two HbA1c observations (Jan and Apr)"
            inv1, inv2 = invs[0], invs[1]

            # Direct evaluation assertion via DifferenceEvaluator
            eval_res = difference_evaluator.evaluate_investigation_difference(
                entity="HbA1c",
                val_a=inv1.value_numeric,
                val_b=inv2.value_numeric,
                unit_a=inv1.unit,
                unit_b=inv2.unit,
                date_a=inv1.observed_date,
                date_b=inv2.observed_date,
            )
            assert eval_res.classification == DifferenceClassification.TREND, (
                "Sequential lab changes across dates must be classified as TREND"
            )
            assert eval_res.is_contradiction is False, (
                "Lab trend must NEVER be classified as a contradiction"
            )

            # Contradiction table assertion
            lab_conflicts = (
                db.query(Contradiction)
                .filter(
                    Contradiction.patient_id == pid, Contradiction.issue_type == "lab_conflict"
                )
                .all()
            )
            assert len(lab_conflicts) == 0, (
                "No lab contradictions should exist for valid chronological HbA1c observations"
            )

        # =========================================================================
        # 7. ASSERTION: MEDICATION CONFLICT REMAINS FLAGGED
        # =========================================================================
        with get_db_context() as db:
            med_conflicts = (
                db.query(Contradiction)
                .filter(
                    Contradiction.patient_id == pid,
                    Contradiction.issue_type == "medication_conflict",
                )
                .all()
            )
            assert len(med_conflicts) >= 1, (
                "Medication discrepancy between 500mg and 1000mg Metformin must be flagged"
            )
            conflict = med_conflicts[0]
            assert conflict.status == "open"
            detail = json.loads(conflict.detail_json)
            # Both conflicting sides must be preserved
            assert "source_1" in detail and "source_2" in detail
            assert "500" in detail["source_1"]["dose"]
            assert "1000" in detail["source_2"]["dose"]
            assert detail.get("preferred_display_order") is not None

        # =========================================================================
        # 8. DOCTOR BRIEF GENERATION & SAFE DETERMINISTIC FALLBACK
        # =========================================================================
        # Trigger brief generation with simulated LLM outage to enforce deterministic fallback hierarchy
        with patch("app.ai.gateway.llm_gateway.complete_json_async", side_effect=Exception("LLM Gateway Unavailable")):
            brief, source = await brief_service.generate_brief(
                db=db,
                patient_id=pid,
                specialty="general_medicine",
                actor="system",
                force_regenerate=True,
            )

        # Brief assertions
        assert source == "fallback_template", "Outage must safely fall back to deterministic template"
        assert brief.generation_source == "fallback_template"
        assert "Deterministic clinical summary" in brief.disclaimer

        # Trend must appear in important_trends with decreasing direction
        assert len(brief.important_trends) >= 1
        hba1c_trend = next(t for t in brief.important_trends if "hba1c" in t.test.lower())
        assert hba1c_trend.direction == "down", "HbA1c 8.4 -> 7.8 must be classified as a downward trend"

        # Contradiction must carry both instructions
        assert len(brief.contradictions) >= 1
        brief_conflict = brief.contradictions[0]
        assert len(brief_conflict.sources) == 2, "Brief must retain both conflicting medication instructions"
        assert brief_conflict.sources[0] != brief_conflict.sources[1]

        # Missing information clearly marked
        assert len(brief.missing_information) >= 1
        assert any("allergy" in m.prompt.lower() or "allergy" in m.reason.lower() for m in brief.missing_information)
        assert len(brief.allergies) >= 1
        assert brief.allergies[0].status == "not_documented"

        # =========================================================================
        # 9. DOCTOR REVIEW & APPROVAL WORKFLOW (Doctor approval is mandatory)
        # =========================================================================
        # A. Create Consultation Draft (Version 1: AI Generated)
        cns_res = client.post(
            f"/api/v1/patients/{pid}/consultations",
            json={"specialty": "general_medicine"},
            headers=auth_header(token_alice),
        )
        assert cns_res.status_code == 201
        cns_data = cns_res.json()["data"]
        cid = cns_data["id"]
        v1 = cns_data["version"]

        assert v1["version_number"] == 1
        assert v1["origin"] == ConsultationOrigin.ai_generated.value
        # Clinical judgment fields must be empty in AI draft
        assert v1["content"]["examination"] == ""
        assert v1["content"]["assessment"] == ""
        assert v1["content"]["plan"] == ""

        # B. Doctor approval is required: Attempt to approve untouched AI draft without acknowledgment fails closed
        unapproved_res = client.post(
            f"/api/v1/consultations/{cid}/approve",
            json={"acknowledged_unedited": False, "expected_version_id": v1["id"]},
            headers=auth_header(token_alice),
        )
        assert unapproved_res.status_code == 422, "Untouched AI draft without acknowledgment must be blocked by Gate 1"

        # C. Doctor edits note: documents exam, assessment, plan, resolving the conflict
        doc_content = dict(v1["content"])
        doc_content["examination"] = "BP: 122/78 mmHg, HR: 74 bpm. Abdomen soft, non-tender."
        doc_content["assessment"] = "Type 2 Diabetes Mellitus with medication dose discrepancy resolved to 500 mg BD."
        doc_content["plan"] = "Continue Metformin 500 mg BD. Repeat HbA1c in 3 months."

        v2_res = client.post(
            f"/api/v1/consultations/{cid}/versions",
            json={
                "content": doc_content,
                "change_summary": "Doctor documented physical exam, resolved medication conflict to 500mg, and defined plan.",
                "expected_version_id": v1["id"],
            },
            headers=auth_header(token_alice),
        )
        assert v2_res.status_code == 200
        v2_data = v2_res.json()["data"]
        v2_id = v2_data["version_id"]
        assert v2_data["version_number"] == 2
        assert v2_data["origin"] == ConsultationOrigin.doctor_edited.value

        # D. Doctor reviews and resolves/acknowledges open high-severity conflicts in the queue
        with get_db_context() as db:
            open_high_conflicts = (
                db.query(Contradiction)
                .filter(
                    Contradiction.patient_id == pid,
                    Contradiction.severity == Severity.high.value,
                    Contradiction.status == "open",
                )
                .all()
            )
            for c in open_high_conflicts:
                print(f"Resolving open conflict: {c.id} - {c.title} ({c.issue_type})")
                patch_res = client.patch(
                    f"/api/v1/issues/{c.id}",
                    json={
                        "status": "resolved",
                        "doctor_note": "Doctor reviewed discrepancy and resolved dosage to Metformin 500 mg BD.",
                    },
                    headers=auth_header(token_alice),
                )
                assert patch_res.status_code == 200

        # E. Gate 1 Validation & Doctor Approval
        with patch("app.validation.gate1_memory.evaluate_gate1_judge", return_value=(True, "info", {"verdict": "pass"})):
            preview_res = client.post(
                f"/api/v1/consultations/{cid}/approve/preview",
                json={"acknowledged_unedited": False},
                headers=auth_header(token_alice),
            )
            assert preview_res.status_code == 200
            assert preview_res.json()["data"]["can_approve"] is True

            approve_res = client.post(
                f"/api/v1/consultations/{cid}/approve",
                json={"acknowledged_unedited": False, "expected_version_id": v2_id},
                headers=auth_header(token_alice),
            )
            assert approve_res.status_code == 200
            assert approve_res.json()["data"]["status"] == "approved"

            # Retrying approval blocked (idempotent / conflict)
            retry_approve = client.post(
                f"/api/v1/consultations/{cid}/approve",
                json={"acknowledged_unedited": False, "expected_version_id": v2_id},
                headers=auth_header(token_alice),
            )
            assert retry_approve.status_code in (409, 422), "Re-approving an already approved consultation must be rejected"

        # =========================================================================
        # 10. ASSERTION: CLINICAL MEMORY CONTAINS ONLY APPROVED/VERIFIED INFORMATION
        # =========================================================================
        with get_db_context() as db:
            memories = db.query(ClinicalMemory).filter(ClinicalMemory.patient_id == pid).all()
            assert len(memories) >= 2, "Approved consultation must create verified clinical memories"

            for m in memories:
                assert m.verified is True, "Clinical memory must only contain verified information"
                assert m.source_consultation_id == cid
                assert m.source_version_id == v2_id
                prov = json.loads(m.content_json).get("provenance", {})
                assert prov.get("approved_by") == alice_id or prov.get("doctor_id") == alice_id

            # Historical information preserved
            versions = db.query(ConsultationVersion).filter(ConsultationVersion.consultation_id == cid).all()
            assert len(versions) == 2, "Both AI draft (v1) and Doctor edit (v2) must be preserved in history"
            v1_db = next(v for v in versions if v.version_number == 1)
            v2_db = next(v for v in versions if v.version_number == 2)
            assert v1_db.origin == ConsultationOrigin.ai_generated.value
            assert v2_db.origin == ConsultationOrigin.doctor_edited.value

        # =========================================================================
        # 11. SECOND CONSULTATION & RETRIEVAL OF PREVIOUS APPROVED MEMORY
        # =========================================================================
        cns2_res = client.post(
            f"/api/v1/patients/{pid}/consultations",
            json={"specialty": "general_medicine"},
            headers=auth_header(token_alice),
        )
        assert cns2_res.status_code == 201
        cns2_data = cns2_res.json()["data"]
        cns2_id = cns2_data["id"]
        assert cns2_id != cid, "Second consultation must receive a distinct unique ID"

        v_cns2 = cns2_data["version"]
        cns2_content = v_cns2["content"]

        # Assert that previous approved clinical memory was retrieved into the new draft
        assert len(cns2_content["verified_memories"]) >= 2, (
            "Second consultation must retrieve previously approved clinical memories"
        )
        assert any(
            m["source_consultation_id"] == cid for m in cns2_content["verified_memories"]
        ), "Retrieved memory items must point to the first approved consultation"

        # Assert past history reflects previous approved memory
        assert "Approved assessment" in cns2_content["past_history"] or "Approved plan" in cns2_content["past_history"], (
            "Past history in second consultation must incorporate previously approved memory"
        )

        # Assert system flag acknowledging retrieved memory
        assert any(
            "approved clinical memory" in f["text"].lower() for f in cns2_content["flags"]
        ), "System flag must acknowledge retrieval of previous approved memory"
