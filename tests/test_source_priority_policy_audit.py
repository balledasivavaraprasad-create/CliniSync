import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_db_context
from app.models.patient import Patient
from app.models.clinical_fact import ClinicalFact
from app.models.medication import Medication
from app.models.investigation import Investigation
from app.models.document import Document
from app.utils.ids import (
    patient_id,
    fact_id,
    medication_id,
    investigation_id,
    document_id,
)
from app.services.contradiction_service import contradiction_service
from app.services.difference_evaluator import difference_evaluator
from app.services.source_priority_policy import (
    source_priority_policy,
    SourceAuthorityLevel,
)
from app.services.brief_service import brief_service, _conflict_sources
import json

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_policy_after_test():
    """Ensure tests always restore default source hierarchy."""
    source_priority_policy.reset_hierarchy_to_default()
    yield
    source_priority_policy.reset_hierarchy_to_default()


def test_source_hierarchy_classification_and_ranking():
    """
    Test 1: Verify correct mapping of sources to authority levels and ranking:
    1. doctor_approved_consultation
    2. doctor_entered
    3. official_clinical_document
    4. lab_report
    5. prescription
    6. patient_reported
    7. ai_inference
    """
    policy = source_priority_policy

    # Verify classification
    assert policy.classify_source_type(is_doctor_verified=True) == SourceAuthorityLevel.DOCTOR_APPROVED_CONSULTATION
    assert policy.classify_source_type(is_doctor_entered=True) == SourceAuthorityLevel.DOCTOR_ENTERED
    assert policy.classify_source_type("consultation_note") == SourceAuthorityLevel.OFFICIAL_CLINICAL_DOCUMENT
    assert policy.classify_source_type("discharge_summary") == SourceAuthorityLevel.OFFICIAL_CLINICAL_DOCUMENT
    assert policy.classify_source_type("lab_report") == SourceAuthorityLevel.LAB_REPORT
    assert policy.classify_source_type("prescription") == SourceAuthorityLevel.PRESCRIPTION
    assert policy.classify_source_type(is_patient_reported=True) == SourceAuthorityLevel.PATIENT_REPORTED
    assert policy.classify_source_type(is_ai_inferred=True) == SourceAuthorityLevel.AI_INFERENCE

    # Verify ranking hierarchy (0 is most authoritative)
    rank_approved = policy.get_authority_rank(SourceAuthorityLevel.DOCTOR_APPROVED_CONSULTATION)
    rank_entered = policy.get_authority_rank(SourceAuthorityLevel.DOCTOR_ENTERED)
    rank_doc = policy.get_authority_rank(SourceAuthorityLevel.OFFICIAL_CLINICAL_DOCUMENT)
    rank_lab = policy.get_authority_rank(SourceAuthorityLevel.LAB_REPORT)
    rank_rx = policy.get_authority_rank(SourceAuthorityLevel.PRESCRIPTION)
    rank_patient = policy.get_authority_rank(SourceAuthorityLevel.PATIENT_REPORTED)
    rank_ai = policy.get_authority_rank(SourceAuthorityLevel.AI_INFERENCE)

    assert rank_approved < rank_entered < rank_doc < rank_lab < rank_rx < rank_patient < rank_ai


def test_conflict_evaluation_retains_all_sources_without_silent_overwrite():
    """
    Test 2: When two sources conflict, the system:
    - Never overwrites or drops either source
    - Deterministically determines which source is more authoritative
    - Places the more authoritative source first in preferred_display_order
    - Flags that doctor review is required
    """
    policy = source_priority_policy

    # Case: Official Consultation Note vs Prescription on same date
    sources = {
        "source_a": {
            "source_type": "prescription",
            "filename": "doc_rx_march.pdf",
            "value": "Metformin 500mg BID",
            "date": "2026-03-15",
        },
        "source_b": {
            "source_type": "consultation_note",
            "filename": "doc_consult_march.pdf",
            "value": "Metformin 1000mg BID",
            "date": "2026-03-15",
        },
    }

    result = policy.evaluate_sources(
        entity="Metformin",
        clinical_field="medication",
        sources=sources,
        is_contradiction=True,
    )

    # Both sources are retained
    assert result.retained_all_sources is True
    assert "source_a" in result.sources
    assert "source_b" in result.sources

    # Official consultation note (source_b) is more authoritative than prescription (source_a)
    assert result.authoritative_source_key == "source_b"
    assert result.authoritative_level == SourceAuthorityLevel.OFFICIAL_CLINICAL_DOCUMENT
    assert result.preferred_display_order == ["source_b", "source_a"]
    assert result.requires_doctor_review is True
    assert "consultation_note" in result.explanation.lower() or "official_clinical_document" in result.explanation.lower()


def test_conflict_with_equal_authority_requires_doctor_review():
    """
    Test 3: When conflicting records share equivalent authority (e.g. two prescriptions with different doses),
    neither is silently crowned as 'correct', and doctor review is required.
    """
    policy = source_priority_policy

    sources = {
        "source_1": {
            "source_type": "prescription",
            "filename": "rx_dr_smith.pdf",
            "value": "Lisinopril 10mg QD",
            "date": "2026-04-01",
        },
        "source_2": {
            "source_type": "prescription",
            "filename": "rx_dr_jones.pdf",
            "value": "Lisinopril 20mg QD",
            "date": "2026-04-01",
        },
    }

    result = policy.evaluate_sources(
        entity="Lisinopril",
        clinical_field="medication",
        sources=sources,
        is_contradiction=True,
    )

    assert result.retained_all_sources is True
    assert result.requires_doctor_review is True
    assert "equivalent authority level" in result.explanation.lower()


def test_difference_evaluator_integrates_source_priority():
    """
    Test 4: Verify that difference_evaluator automatically enriches results with source priority metadata.
    """
    doc_a = {"document_type": "prescription", "filename": "doc_rx.pdf"}
    doc_b = {"document_type": "consultation_note", "filename": "doc_clinic.pdf"}

    res = difference_evaluator.evaluate_medication_difference(
        entity="Amlodipine",
        dose_a="5 mg",
        dose_b="10 mg",
        freq_a="QD",
        freq_b="QD",
        date_a="2026-02-01",
        date_b="2026-02-01",
        doc_a_meta=doc_a,
        doc_b_meta=doc_b,
    )

    assert res.is_contradiction is True
    assert res.authoritative_source == "source_b"
    assert res.preferred_display_order == ["source_b", "source_a"]
    assert res.requires_doctor_review is True
    assert res.source_priority_explanation is not None


def test_configurable_hierarchy_override():
    """
    Test 5: Verify that the source hierarchy is dynamically configurable and not hardcoded.
    If an institution prioritizes lab reports over clinical consultation notes:
    lab_report > official_clinical_document.
    """
    custom_hierarchy = [
        "lab_report",
        "official_clinical_document",
        "prescription",
        "patient_reported",
        "ai_inference",
    ]
    source_priority_policy.set_hierarchy(custom_hierarchy)

    sources = {
        "source_a": {
            "source_type": "consultation_note",
            "filename": "consultation.pdf",
            "value": "HbA1c 7.5",
        },
        "source_b": {
            "source_type": "lab_report",
            "filename": "lab_results.pdf",
            "value": "HbA1c 6.8",
        },
    }

    result = source_priority_policy.evaluate_sources(
        entity="HbA1c",
        clinical_field="investigation",
        sources=sources,
        is_contradiction=True,
    )

    # With the custom hierarchy, lab_report (source_b) is authoritative over consultation_note (source_a)
    assert result.authoritative_source_key == "source_b"
    assert result.preferred_display_order == ["source_b", "source_a"]


def test_brief_service_presents_sources_in_authoritative_order():
    """
    Test 6: Verify that the brief service displays conflicting sources side-by-side
    in preferred authoritative order while retaining all sources.
    """
    detail = {
        "preferred_display_order": ["source_b", "source_a"],
        "source_a": {"doc": "Prescription Doc", "dose": "500 mg", "freq": "OD"},
        "source_b": {"doc": "Consultation Doc", "dose": "1000 mg", "freq": "BID"},
    }
    lines = _conflict_sources(json.dumps(detail))
    assert len(lines) == 2
    # Preferred source_b is presented first
    assert "1000 mg" in lines[0]
    assert "Consultation Doc" in lines[0]
    # source_a is preserved
    assert "500 mg" in lines[1]
    assert "Prescription Doc" in lines[1]


def test_source_priority_policy_api_endpoints():
    """
    Test 7: Test GET and PUT /api/v1/issues/source-priority-policy
    """
    # 1. GET current hierarchy
    res = client.get("/api/v1/issues/source-priority-policy")
    assert res.status_code == 200
    data = res.json()["data"]
    assert "hierarchy" in data
    assert "doctor_approved_consultation" in data["hierarchy"]
    assert "ai_inference" in data["hierarchy"]

    # 2. PUT new hierarchy
    new_hierarchy = [
        "doctor_entered",
        "doctor_approved_consultation",
        "official_clinical_document",
        "lab_report",
        "prescription",
        "patient_reported",
        "ai_inference"
    ]
    put_res = client.put(
        "/api/v1/issues/source-priority-policy",
        json={"hierarchy": new_hierarchy}
    )
    assert put_res.status_code == 200
    assert put_res.json()["data"]["hierarchy"] == new_hierarchy

    # Verify that policy reflects update
    assert source_priority_policy.hierarchy == new_hierarchy
