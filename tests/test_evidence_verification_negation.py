import datetime
from typing import Tuple
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.database import get_db_context
from app.models.patient import Patient
from app.models.document import Document, DocumentPage
from app.models.clinical_fact import ClinicalFact
from app.utils.ids import patient_id, document_id, page_id, fact_id
from app.services.evidence_service import (
    evidence_service,
    EvidenceSupportStatus,
)


@pytest.fixture
def make_patient():
    def _create(db: Session, name: str = "Evidence Verification Test Patient") -> Patient:
        p = Patient(id=patient_id(), full_name=name)
        db.add(p)
        db.flush()
        return p
    return _create


@pytest.fixture
def make_doc_with_page():
    def _create(db: Session, pid: str, filename: str, page_text: str) -> Tuple[Document, DocumentPage]:
        doc = Document(
            id=document_id(),
            patient_id=pid,
            original_filename=filename,
            stored_path=f"storage/{filename}",
            mime_type="application/pdf",
            file_size=1024,
            sha256=f"sha_{filename}",
            processing_status="complete"
        )
        db.add(doc)
        db.flush()

        p = DocumentPage(
            id=page_id(),
            document_id=doc.id,
            page_number=1,
            text=page_text
        )
        db.add(p)
        db.flush()
        return doc, p
    return _create


# ---------------------------------------------------------------------------
# Negation Tests specifically requested by prompt
# ---------------------------------------------------------------------------

def test_negation_no_fever_must_not_support_fever_present():
    """
    Source: "no fever"
    Claim: "fever present"
    Must NOT support claim. Evidence explicitly contradicts claim.
    """
    source_text = "Patient reports no fever over the past 48 hours."
    claim = "fever present"
    pages_dict = {1: source_text}

    res = evidence_service.verify_evidence(
        source_text=source_text,
        page_number=1,
        pages_dict=pages_dict,
        expected_content=claim
    )

    assert res.verified is False
    assert res.evidence_found is True
    assert res.evidence_supports_claim is False
    assert res.evidence_contradicts_claim is True
    assert res.support_status == EvidenceSupportStatus.CONTRADICTS
    assert res.verification_level == 4
    assert "contradicts" in res.unsupported_reason.lower() or "negates" in res.unsupported_reason.lower()


def test_negation_no_evidence_of_pneumonia_must_not_support_pneumonia_diagnosed():
    """
    Source: "No evidence of pneumonia."
    Claim: "pneumonia diagnosed"
    Must NOT support claim.
    """
    source_text = "Chest X-ray: No evidence of pneumonia or pleural effusion."
    claim = "pneumonia diagnosed"
    pages_dict = {1: source_text}

    res = evidence_service.verify_evidence(
        source_text=source_text,
        page_number=1,
        pages_dict=pages_dict,
        expected_content=claim
    )

    assert res.verified is False
    assert res.evidence_found is True
    assert res.evidence_supports_claim is False
    assert res.evidence_contradicts_claim is True
    assert res.support_status == EvidenceSupportStatus.CONTRADICTS
    assert res.verification_level == 4
    assert "pneumonia" in res.unsupported_reason.lower()


def test_negation_no_evidence_of_pneumonia_must_not_support_patient_has_pneumonia():
    """
    Source: "No evidence of pneumonia."
    Claim: "Patient has pneumonia."
    """
    source_text = "No evidence of pneumonia."
    claim = "Patient has pneumonia."
    pages_dict = {1: f"Findings: {source_text}"}

    res = evidence_service.verify_evidence(
        source_text=source_text,
        page_number=1,
        pages_dict=pages_dict,
        expected_content=claim
    )

    assert res.verified is False
    assert res.evidence_supports_claim is False
    assert res.evidence_contradicts_claim is True
    assert res.support_status == EvidenceSupportStatus.CONTRADICTS
    assert res.verification_level == 4


def test_context_history_of_diabetes_must_not_support_current_uncontrolled_diabetes():
    """
    Source: "history of diabetes"
    Claim: "current uncontrolled diabetes"
    Must NOT support claim. Evidence states history, which does not substantiate acute uncontrolled state.
    """
    source_text = "Past medical history is notable for history of diabetes mellitus."
    claim = "current uncontrolled diabetes"
    pages_dict = {1: source_text}

    res = evidence_service.verify_evidence(
        source_text=source_text,
        page_number=1,
        pages_dict=pages_dict,
        expected_content=claim
    )

    assert res.verified is False
    assert res.evidence_found is True
    assert res.evidence_supports_claim is False
    assert res.evidence_insufficient is True
    assert res.support_status == EvidenceSupportStatus.INSUFFICIENT
    assert res.verification_level == 4
    assert "uncontrolled" in res.unsupported_reason.lower() or "insufficient" in res.unsupported_reason.lower()


# ---------------------------------------------------------------------------
# Layered Verification Strategy: Levels 1, 2, 3, 4
# ---------------------------------------------------------------------------

def test_level_1_exact_text_match():
    """
    LEVEL 1: Exact or normalized text match.
    """
    page_text = "Assessment: Patient has confirmed Type 2 Diabetes Mellitus."
    source_text = "Type 2 Diabetes Mellitus"
    claim = "Type 2 Diabetes Mellitus"
    pages_dict = {1: page_text}

    res = evidence_service.verify_evidence(
        source_text=source_text,
        page_number=1,
        pages_dict=pages_dict,
        expected_content=claim
    )

    assert res.verified is True
    assert res.evidence_found is True
    assert res.evidence_supports_claim is True
    assert res.support_status == EvidenceSupportStatus.SUPPORTS
    assert res.verification_level == 1
    assert res.score >= 99.0


def test_level_2_and_3_fuzzy_and_semantic_positive_match():
    """
    LEVEL 2 & 3: Fuzzy text match with semantic alignment.
    """
    page_text = "Prescribed Tab Metformin  500mg   twice daily with breakfast."
    source_text = "Tab Metformin 500mg twice daily"
    claim = "metformin 500mg"
    pages_dict = {1: page_text}

    res = evidence_service.verify_evidence(
        source_text=source_text,
        page_number=1,
        pages_dict=pages_dict,
        expected_content=claim
    )

    assert res.verified is True
    assert res.evidence_found is True
    assert res.evidence_supports_claim is True
    assert res.support_status == EvidenceSupportStatus.SUPPORTS
    assert res.verification_level in (1, 2, 3)


def test_level_4_insufficient_evidence_unverified():
    """
    LEVEL 4: If evidence cannot sufficiently support the claim -> mark as UNVERIFIED.
    """
    page_text = "Patient evaluated for routine wellness exam. No acute issues."
    source_text = "acute myocardial infarction"
    pages_dict = {1: page_text}

    res = evidence_service.verify_evidence(
        source_text=source_text,
        page_number=1,
        pages_dict=pages_dict,
        expected_content="myocardial infarction"
    )

    assert res.verified is False
    assert res.verification_level == 4
    assert res.evidence_found is False
    assert res.support_status == EvidenceSupportStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# Fact Retention of all 8 Provenance Attributes
# ---------------------------------------------------------------------------

def test_fact_retains_all_eight_provenance_attributes(make_patient):
    """
    Every clinically meaningful extracted fact should retain:
    - source document ID
    - source page
    - source span
    - source text
    - extraction method
    - extraction confidence
    - verification status
    - verification timestamp where appropriate
    """
    with get_db_context() as db:
        p = make_patient(db)
        doc = Document(
            id=document_id(),
            patient_id=p.id,
            original_filename="discharge_summary.pdf",
            stored_path="storage/dummy.pdf",
            mime_type="application/pdf",
            file_size=1024,
            sha256="sha_test_dummy",
            processing_status="complete"
        )
        db.add(doc)
        db.flush()

        fact = ClinicalFact(
            id=fact_id(),
            patient_id=p.id,
            document_id=doc.id,
            fact_type="diagnosis",
            value="Essential Hypertension",
            source_text="Patient diagnosed with Essential Hypertension.",
            source_page=2,
            source_span_start=15,
            source_span_end=60,
            confidence=0.96,
            provenance_verified=True,
            verification_status="documented",
            extraction_model="gpt-4o",
            extraction_run_id="run_12345"
        )
        db.add(fact)
        db.commit()

        # Verify all 8 fields on model
        assert fact.document_id == doc.id
        assert fact.source_page == 2
        assert fact.source_span == {"start": 15, "end": 60}
        assert fact.source_span_start == 15
        assert fact.source_span_end == 60
        assert fact.source_text == "Patient diagnosed with Essential Hypertension."
        assert fact.extraction_method == "gpt-4o"
        assert fact.confidence == 0.96
        assert fact.verification_status == "documented"
        assert fact.verification_timestamp is not None
        assert fact.semantic_state == "DOCUMENTED"


def test_fact_evidence_endpoint_exposes_provenance_attributes():
    """
    API test: GET /api/v1/patients/{pid}/facts and /api/v1/facts/{fact_id}/evidence
    return all 8 required provenance fields.
    """
    client = TestClient(app)
    with get_db_context() as db:
        pid = patient_id()
        p = Patient(id=pid, full_name="Provenance Endpoint Patient")
        doc_id = document_id()
        doc = Document(
            id=doc_id,
            patient_id=pid,
            original_filename="notes.pdf",
            stored_path="storage/notes.pdf",
            mime_type="application/pdf",
            file_size=1024,
            sha256="sha_prov_api",
            processing_status="complete",
        )
        fid = fact_id()
        fact = ClinicalFact(
            id=fid,
            patient_id=pid,
            document_id=doc_id,
            fact_type="diagnosis",
            value="Type 2 Diabetes Mellitus",
            source_text="Patient has Type 2 Diabetes Mellitus diagnosed in 2020.",
            source_page=1,
            source_span_start=12,
            source_span_end=54,
            extraction_model="gpt-4o",
            confidence=0.98,
            verification_status="documented",
            provenance_verified=True,
        )
        db.add(p)
        db.add(doc)
        db.add(fact)
        db.commit()

    res = client.get(f"/api/v1/patients/{pid}/facts")
    assert res.status_code == 200
    facts = res.json()["data"]
    assert len(facts) > 0

    first_fact = facts[0]
    assert first_fact["id"] == fid
    assert first_fact["document_id"] == doc_id
    assert first_fact["source_page"] == 1
    assert first_fact["source_span"] == {"start": 12, "end": 54}
    assert "Type 2 Diabetes" in first_fact["source_text"]
    assert first_fact["extraction_method"] == "gpt-4o"
    assert first_fact["extraction_confidence"] == 0.98
    assert first_fact["verification_status"] == "documented"
    assert first_fact["verification_timestamp"] is not None
    assert first_fact["semantic_state"] == "DOCUMENTED"

    # Also test GET /api/v1/facts/{fact_id}/evidence
    ev_res = client.get(f"/api/v1/facts/{fid}/evidence")
    assert ev_res.status_code == 200
    ev_data = ev_res.json()["data"]
    assert ev_data["source_document_id"] == doc_id
    assert ev_data["source_page"] == 1
    assert ev_data["source_span"] == {"start": 12, "end": 54}
    assert ev_data["extraction_method"] == "gpt-4o"
    assert ev_data["verification_status"] == "documented"
