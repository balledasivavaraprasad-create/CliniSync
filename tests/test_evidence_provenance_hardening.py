"""
Comprehensive Evidence and Provenance Hardening Test Suite for ClinSync.

Validates that:
1. Exact evidence matching finds exact character spans and returns 1.0 score.
2. Fuzzy evidence matching aligns spans and handles OCR/whitespace discrepancies.
3. Unsupported extractions (hallucinations/unsupported citations) fail verification and are capped at <= 0.50 confidence.
4. Wrong page citations are resolved to the correct page across multi-page documents.
5. Missing or empty evidence fails verification gracefully.
6. Confidence downgrade strictly enforces the 0.50 cap for unverified provenance regardless of raw LLM confidence.
7. Evidence ID resolution endpoint (GET /api/v1/facts/{fact_id}/evidence) resolves valid spans and enforces authorization.
8. Provenance preservation end-to-end chain:
   Document -> Evidence -> ClinicalFact -> Longitudinal Object (Medication/Investigation) -> DoctorBrief -> Evidence Endpoint.
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_db_context
from app.models.user import User
from app.models.patient import Patient
from app.models.patient_access import PatientAccess
from app.models.document import Document, DocumentPage
from app.models.clinical_fact import ClinicalFact
from app.models.medication import Medication
from app.models.investigation import Investigation
from app.models.brief import Brief
from app.utils.hashing import hash_password
from app.utils.tokens import create_access_token
from app.utils.ids import (
    user_id,
    patient_id,
    document_id,
    page_id,
    clinical_fact_id,
    medication_id,
    brief_id,
)
from app.utils.text import verify_provenance_text
from app.services.evidence_service import evidence_service
from app.services.confidence_service import confidence_service
from app.services.brief_service import brief_service
from app.validation.gate2_output import gate2_validator
from app.db.seed import seed_demo_data, DEMO_PATIENT_ID

client = TestClient(app)


def auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


class TestEvidenceAlignmentAndVerification:
    """Tests exact & fuzzy span alignment and source content verification."""

    def test_exact_evidence_match(self):
        page_text = "The patient was evaluated and started on Metformin 500mg twice daily with meals."
        target_citation = "Metformin 500mg twice daily"

        is_verified, score, start, end = verify_provenance_text(target_citation, page_text)
        assert is_verified is True
        assert score >= 90.0
        assert start is not None and end is not None
        assert page_text[start:end] == target_citation

    def test_fuzzy_evidence_match(self):
        page_text = "Patient was prescribed  Metformin   500 mg  twice daily   after lunch."
        target_citation = "Metformin 500 mg twice daily"

        is_verified, score, start, end = verify_provenance_text(target_citation, page_text, threshold=80)
        assert is_verified is True
        assert score >= 80.0
        assert start is not None and end is not None
        matched_substr = page_text[start:end]
        assert "Metformin" in matched_substr
        assert "twice daily" in matched_substr

    def test_unsupported_extraction(self):
        """When the LLM cites text that does not support the extracted entity, verification fails."""
        doc_id = document_id()
        p_id = patient_id()

        with get_db_context() as db:
            p = Patient(id=p_id, full_name="Test Patient Unsupported", date_of_birth="1985-02-01")
            doc = Document(
                id=doc_id,
                patient_id=p_id,
                original_filename="discharge_summary.pdf",
                stored_path="/tmp/fake.pdf",
                mime_type="application/pdf",
                file_size=1024,
                sha256="fake_sha256_unsupported",
                document_type="discharge_summary",
                processing_status="completed",
            )
            page = DocumentPage(
                id=page_id(),
                document_id=doc_id,
                page_number=1,
                text="Patient has hypertension and takes Lisinopril 10mg daily. No lipid lowering drugs.",
            )
            db.add_all([p, doc, page])
            db.commit()

            # Extracted entity is Atorvastatin 40mg, but cited source text only talks about Lisinopril
            res = evidence_service.verify_evidence(
                db=db,
                document_id=doc_id,
                source_page=1,
                source_text="takes Lisinopril 10mg daily",
                expected_content="Atorvastatin 40mg",
            )

            assert res.verified is False
            assert "not support" in (res.unsupported_reason or "").lower()

    def test_wrong_page_resolution(self):
        """When extraction cites page 1 but text is on page 2, evidence service resolves page 2."""
        doc_id = document_id()
        p_id = patient_id()

        with get_db_context() as db:
            p = Patient(id=p_id, full_name="Test Patient Wrong Page", date_of_birth="1978-04-12")
            doc = Document(
                id=doc_id,
                patient_id=p_id,
                original_filename="lab_report.pdf",
                stored_path="/tmp/fake2.pdf",
                mime_type="application/pdf",
                file_size=1024,
                sha256="fake_sha256_wrongpage",
                document_type="lab_report",
                processing_status="completed",
            )
            p1 = DocumentPage(
                id=page_id(),
                document_id=doc_id,
                page_number=1,
                text="General physical examination: Pulse 72 bpm, BP 120/80 mmHg.",
            )
            p2 = DocumentPage(
                id=page_id(),
                document_id=doc_id,
                page_number=2,
                text="Endocrinology Panel: Glycated Hemoglobin HbA1c 7.8% (ref: < 5.7%).",
            )
            db.add_all([p, doc, p1, p2])
            db.commit()

            res = evidence_service.verify_evidence(
                db=db,
                document_id=doc_id,
                source_page=1,  # cites page 1 mistakenly
                source_text="Glycated Hemoglobin HbA1c 7.8%",
                expected_content="HbA1c 7.8%",
            )

            assert res.verified is True
            assert res.page == 2  # Correctly resolved to page 2
            assert res.span_start is not None and res.span_end is not None

    def test_missing_evidence(self):
        """Missing or empty evidence fails gracefully with verified=False."""
        doc_id = document_id()
        p_id = patient_id()

        with get_db_context() as db:
            p = Patient(id=p_id, full_name="Test Patient Missing", date_of_birth="1990-10-10")
            doc = Document(
                id=doc_id,
                patient_id=p_id,
                original_filename="empty.pdf",
                stored_path="/tmp/fake3.pdf",
                mime_type="application/pdf",
                file_size=1024,
                sha256="fake_sha256_empty",
                document_type="other",
                processing_status="completed",
            )
            db.add_all([p, doc])
            db.commit()

            # Empty text
            res_empty = evidence_service.verify_evidence(
                db=db,
                document_id=doc_id,
                source_page=1,
                source_text="",
            )
            assert res_empty.verified is False

            # None text
            res_none = evidence_service.verify_evidence(
                db=db,
                document_id=doc_id,
                source_page=1,
                source_text=None,
            )
            assert res_none.verified is False

            # Non-existent document
            res_no_doc = evidence_service.verify_evidence(
                db=db,
                document_id="doc_non_existent",
                source_page=1,
                source_text="Some text",
            )
            assert res_no_doc.verified is False


class TestConfidenceHardening:
    """Tests confidence scoring logic, source quality, ambiguity penalties, and strict caps."""

    def test_confidence_downgrade_unverified_provenance(self):
        """If provenance is unverified, confidence must be strictly capped at <= 0.50 (needs_verification)."""
        score, band = confidence_service.calculate_confidence(
            model_confidence=0.99,
            provenance_verified=False,
        )
        assert score <= 0.50
        assert band.value == "needs_verification"

    def test_high_confidence_retained_when_provenance_verified(self):
        """When provenance is verified and fact is unambiguous, high confidence is preserved."""
        score, band = confidence_service.calculate_confidence(
            model_confidence=0.95,
            provenance_verified=True,
            source_quality=1.0,
        )
        assert score >= 0.85
        assert band.value == "high"

    def test_source_quality_and_ambiguity_penalties(self):
        """Ambiguity penalties (hedging, low OCR quality) lower confidence appropriately."""
        score, band = confidence_service.calculate_confidence(
            model_confidence=0.90,
            provenance_verified=True,
            ambiguity_penalty=0.15,
            source_quality=0.65,
        )
        assert score < 0.85
        assert band.value in ("medium", "low", "needs_verification")


class TestEvidenceIdResolutionAndAuthorization:
    """Tests the GET /api/v1/facts/{fact_id}/evidence endpoint and IDOR protections."""

    @pytest.fixture(autouse=True)
    def setup_records(self):
        with get_db_context() as db:
            # Users
            u_doc_id = user_id()
            u_other_id = user_id()
            p_id = patient_id()
            d_id = document_id()
            f_id = clinical_fact_id()
            self.u_doc = User(
                id=u_doc_id,
                email=f"dr_prov_{u_doc_id}@clinsync.health",
                full_name="Dr. Provenance Doc",
                role="doctor",
                hashed_password=hash_password("DocPass123!"),
                is_active=True,
            )
            self.u_other = User(
                id=u_other_id,
                email=f"dr_unauth_{u_other_id}@clinsync.health",
                full_name="Dr. Unauthorized",
                role="doctor",
                hashed_password=hash_password("DocPass123!"),
                is_active=True,
            )
            # Patient
            pat = Patient(
                id=p_id,
                full_name="Provenance Patient",
                date_of_birth="1980-05-15",
                sex="female",
            )
            # Access: only u_doc has access
            access = PatientAccess(
                user_id=u_doc_id,
                patient_id=p_id,
                access_level="write",
            )
            # Document
            doc = Document(
                id=d_id,
                patient_id=p_id,
                original_filename="prescription_slip.pdf",
                stored_path="/tmp/presc.pdf",
                mime_type="application/pdf",
                file_size=1024,
                sha256=f"fake_sha256_{d_id}",
                document_type="prescription",
                processing_status="completed",
            )
            self.page_txt = "Rx: Glimepiride 2mg orally once daily before breakfast."
            page = DocumentPage(
                id=page_id(),
                document_id=d_id,
                page_number=1,
                text=self.page_txt,
            )
            # Clinical Fact with exact spans
            span_start = self.page_txt.find("Glimepiride 2mg")
            span_end = span_start + len("Glimepiride 2mg orally once daily")
            fact = ClinicalFact(
                id=f_id,
                patient_id=p_id,
                document_id=d_id,
                fact_type="medication",
                value="Glimepiride 2mg orally once daily",
                source_text="Glimepiride 2mg orally once daily",
                source_page=1,
                source_span_start=span_start,
                source_span_end=span_end,
                confidence=0.96,
                confidence_band="high",
                provenance_verified=True,
                verification_status="verified",
            )
            db.add_all([self.u_doc, self.u_other, pat, access, doc, page, fact])
            db.commit()

            self.fact_id = f_id
            self.doc_id = d_id
            self.patient_id = p_id
            self.u_doc_id = u_doc_id
            self.u_other_id = u_other_id

        self.token_doc = create_access_token(subject=self.u_doc_id, claims={"role": "doctor"})
        self.token_other = create_access_token(subject=self.u_other_id, claims={"role": "doctor"})

    def test_evidence_id_resolution_success(self):
        resp = client.get(
            f"/api/v1/facts/{self.fact_id}/evidence",
            headers=auth_header(self.token_doc),
        )
        assert resp.status_code == 200
        res = resp.json()
        assert res["success"] is True
        ev = res["data"]
        assert ev["fact_id"] == self.fact_id
        assert ev["fact_type"] == "medication"
        assert ev["provenance_verified"] is True
        assert ev["verification_status"] == "verified"
        assert ev["confidence"] == 0.96

        src = ev["source"]
        assert src["document_id"] == self.doc_id
        assert src["document_filename"] == "prescription_slip.pdf"
        assert src["page_number"] == 1
        assert src["verbatim_text"] == "Glimepiride 2mg orally once daily"
        assert src["span_start"] == self.page_txt.find("Glimepiride 2mg")
        assert src["span_end"] == src["span_start"] + len("Glimepiride 2mg orally once daily")

    def test_evidence_id_resolution_idor_blocked(self):
        """Unauthorized doctor cannot query evidence for another patient's fact."""
        resp = client.get(
            f"/api/v1/facts/{self.fact_id}/evidence",
            headers=auth_header(self.token_other),
        )
        assert resp.status_code == 403

    def test_seeded_brief_evidence_shortcuts_resolve(self):
        """Verify that all evidence shortcuts in the demo brief point to real persisted clinical facts."""
        seed_demo_data(reset=True)
        resp = client.get(f"/api/v1/patients/{DEMO_PATIENT_ID}/brief/latest")
        assert resp.status_code == 200
        brief = resp.json()["data"]

        shortcuts = brief.get("evidence_shortcuts", [])
        assert len(shortcuts) > 0

        # Login as demo user or assigned doctor to check facts
        # Default demo patient is accessible to doctors or demo user
        with get_db_context() as db:
            for sc in shortcuts:
                eid = sc["evidence_id"]
                # Must not be a fake demo string
                assert not eid.startswith("ev_00"), f"Found ungrounded fake evidence ID: {eid}"
                fact = db.query(ClinicalFact).filter(ClinicalFact.id == eid).first()
                assert fact is not None, f"Evidence shortcut {eid} does not exist in DB!"
                assert fact.patient_id == DEMO_PATIENT_ID
                assert fact.source_span_start is not None
                assert fact.source_span_end is not None


class TestProvenancePreservationEndToEnd:
    """Tests provenance chain: Document -> Evidence -> ClinicalFact -> Longitudinal Object -> DoctorBrief."""

    def test_provenance_preservation_through_doctor_brief(self):
        with get_db_context() as db:
            p = Patient(
                id=patient_id(),
                full_name="Longitudinal Chain Patient",
                date_of_birth="1975-01-01",
                sex="male",
            )
            doc = Document(
                id=document_id(),
                patient_id=p.id,
                original_filename="consultation_note.pdf",
                stored_path="/tmp/cnote.pdf",
                mime_type="application/pdf",
                file_size=1024,
                sha256="fake_sha256_cnote",
                document_type="progress_note",
                processing_status="completed",
            )
            txt = "Plan: Metformin 850mg orally twice daily. HbA1c was 8.1%."
            page = DocumentPage(
                id=page_id(),
                document_id=doc.id,
                page_number=1,
                text=txt,
            )
            db.add_all([p, doc, page])
            db.commit()

            # 1. Fact creation with exact spans
            m_start = txt.find("Metformin 850mg")
            m_end = m_start + len("Metformin 850mg orally twice daily")
            f_med = ClinicalFact(
                id=clinical_fact_id(),
                patient_id=p.id,
                document_id=doc.id,
                fact_type="medication",
                value="Metformin 850mg orally twice daily",
                source_text="Metformin 850mg orally twice daily",
                source_page=1,
                source_span_start=m_start,
                source_span_end=m_end,
                confidence=0.95,
                confidence_band="high",
                provenance_verified=True,
                verification_status="verified",
            )
            db.add(f_med)
            db.commit()

            # 2. Longitudinal Object creation linked to ClinicalFact
            med = Medication(
                id=medication_id(),
                patient_id=p.id,
                canonical_name="metformin",
                raw_name="Metformin 850mg",
                dose_text="850mg",
                frequency_text="twice daily",
                strength_value=850.0,
                strength_unit="mg",
                status="active",
                group_key="metformin_oral",
                confidence=0.95,
                source_document_id=doc.id,
                fact_id=f_med.id,
            )
            db.add(med)
            db.commit()

            # 3. Doctor Brief generation
            brief = brief_service._build_deterministic_template_brief(
                patient=p,
                specialty="Internal Medicine",
                facts=[f_med],
                meds=[med],
                invs=[],
                issues=[],
            )

            # 4. Gate 2 validation passes
            outcome, checks, report_id = gate2_validator.validate_brief(
                db=db,
                patient_id=p.id,
                brief_data=brief.model_dump(),
                run_judge=False,
            )
            assert outcome.value == "pass"

            # 5. Verify the medication item preserves the evidence_id referencing f_med.id
            med_items = [m for m in brief.current_medications if m.name.lower() == "metformin"]
            assert len(med_items) == 1
            assert f_med.id in med_items[0].evidence_ids

            # 6. Verify evidence shortcut resolves to f_med.id
            shortcut = next((s for s in brief.evidence_shortcuts if s.evidence_id == f_med.id), None)
            assert shortcut is not None
            assert shortcut.document_id == doc.id
            assert shortcut.page == 1
