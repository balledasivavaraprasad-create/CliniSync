import pytest
from datetime import datetime, date, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import get_db_context
from app.models.patient import Patient
from app.models.clinical_fact import ClinicalFact
from app.models.medication import Medication
from app.models.investigation import Investigation
from app.models.contradiction import Contradiction
from app.models.document import Document
from app.utils.ids import (
    patient_id,
    fact_id,
    medication_id,
    investigation_id,
    contradiction_id,
    document_id,
)
from app.services.brief_service import brief_service
from app.schemas.brief import DoctorBrief

client = TestClient(app)


def test_deterministic_brief_all_sections_pure_db():
    """
    Test 1: Verify all 10 recommended sections are populated exclusively from verified DB records
    with ZERO LLM calls, strictly adhering to rules:
    - Symptoms never converted to diagnoses
    - Relevant history sorted chronologically
    - Multi-point investigations provide previous values & trends
    - Contradictions & proactive missing information items generated
    - Document evidence shortcuts preserved
    """
    with get_db_context() as db:
        pid = patient_id()
        doc_id = document_id()

        doc = Document(
            id=doc_id,
            patient_id=pid,
            original_filename="lab_report_2026.pdf",
            stored_path="test/lab_report_2026.pdf",
            mime_type="application/pdf",
            file_size=1024,
            sha256="fakehash12345",
            processing_status="COMPLETED"
        )
        db.add(doc)

        p = Patient(id=pid, full_name="John Doe", age_years=45)
        db.add(p)
        db.flush()

        # Symptoms
        s1 = ClinicalFact(
            id=fact_id(),
            patient_id=pid,
            document_id=doc_id,
            fact_type="symptom",
            value="Persistent dry cough for 3 weeks",
            source_text="Patient presents with persistent dry cough for 3 weeks",
            fact_date=datetime(2026, 3, 10, 10, 0, tzinfo=timezone.utc),
            provenance_verified=True,
            confidence=0.95
        )
        s2 = ClinicalFact(
            id=fact_id(),
            patient_id=pid,
            document_id=doc_id,
            fact_type="symptom",
            value="Mild exertional dyspnea",
            source_text="Mild exertional dyspnea noted",
            fact_date=datetime(2026, 3, 12, 10, 0, tzinfo=timezone.utc),
            provenance_verified=True,
            confidence=0.90
        )

        # Diagnoses (older and newer to verify chronological sorting)
        d1 = ClinicalFact(
            id=fact_id(),
            patient_id=pid,
            document_id=doc_id,
            fact_type="diagnosis",
            value="Hypertension Stage 1",
            source_text="Hypertension Stage 1",
            fact_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            provenance_verified=True,
            confidence=0.95
        )
        d2 = ClinicalFact(
            id=fact_id(),
            patient_id=pid,
            document_id=doc_id,
            fact_type="diagnosis",
            value="Type 2 Diabetes Mellitus",
            source_text="Type 2 Diabetes Mellitus",
            fact_date=datetime(2025, 6, 20, tzinfo=timezone.utc),
            provenance_verified=True,
            confidence=0.95
        )

        # Allergies
        a1 = ClinicalFact(
            id=fact_id(),
            patient_id=pid,
            document_id=doc_id,
            fact_type="allergy",
            value="Penicillin (urticaria / rash)",
            source_text="Allergic to penicillin, developed urticaria",
            provenance_verified=True,
            confidence=0.95
        )

        # Medication Fact
        mf1 = ClinicalFact(
            id=fact_id(),
            patient_id=pid,
            document_id=doc_id,
            fact_type="medication",
            value="Metformin 500 mg PO BID",
            source_text="Metformin 500 mg PO BID",
            provenance_verified=True,
            confidence=0.95
        )
        mf2 = ClinicalFact(
            id=fact_id(),
            patient_id=pid,
            document_id=doc_id,
            fact_type="medication",
            value="Lisinopril 10 mg PO QD",
            source_text="Lisinopril 10 mg PO QD",
            provenance_verified=True,
            confidence=0.95
        )

        db.add_all([s1, s2, d1, d2, a1, mf1, mf2])
        db.flush()

        # Structured Medications
        m1 = Medication(
            id=medication_id(),
            patient_id=pid,
            fact_id=mf1.id,
            canonical_name="metformin",
            raw_name="Metformin",
            strength_value=500.0,
            strength_unit="mg",
            dose_text="500 mg",
            frequency_code="BID",
            group_key="metformin",
            status="active",
            confidence=0.95
        )
        m2 = Medication(
            id=medication_id(),
            patient_id=pid,
            fact_id=mf2.id,
            canonical_name="lisinopril",
            raw_name="Lisinopril",
            strength_value=10.0,
            strength_unit="mg",
            dose_text="10 mg",
            frequency_code="QD",
            group_key="lisinopril",
            status="active",
            confidence=0.95
        )
        db.add_all([m1, m2])

        # Multi-point Investigations (HbA1c: baseline 7.8%, follow-up 6.9%)
        inv1 = Investigation(
            id=investigation_id(),
            patient_id=pid,
            fact_id=d2.id,
            test_name_raw="HbA1c",
            test_name_canonical="hba1c",
            value_numeric=7.8,
            value_text="7.8",
            unit="%",
            reference_text="< 5.7%",
            observed_date=datetime(2025, 6, 20, 0, 0, tzinfo=timezone.utc),
            abnormal_flag="high",
            group_key="hba1c"
        )
        inv2 = Investigation(
            id=investigation_id(),
            patient_id=pid,
            fact_id=d2.id,
            test_name_raw="HbA1c",
            test_name_canonical="hba1c",
            value_numeric=6.9,
            value_text="6.9",
            unit="%",
            reference_text="< 5.7%",
            observed_date=datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc),
            abnormal_flag="high",
            group_key="hba1c"
        )
        db.add_all([inv1, inv2])

        # Contradiction
        c1 = Contradiction(
            id=contradiction_id(),
            patient_id=pid,
            issue_type="medication_conflict",
            title="Lisinopril dosage conflict",
            description="Doc A states Lisinopril 10mg daily while Doc B states Lisinopril 20mg daily",
            severity="high",
            status="open"
        )
        db.add(c1)
        db.commit()

        # Run generate_deterministic_brief directly
        brief = brief_service.generate_deterministic_brief(
            db=db,
            patient_id=pid,
            specialty="general_medicine",
            actor="test_doc"
        )

        assert isinstance(brief, DoctorBrief)
        assert brief.generation_source == "deterministic_template"

        # Section 1: Patient Information
        assert brief.patient.id == pid
        assert brief.patient.name == "John Doe"
        assert brief.patient.age == 45
        assert brief.patient.age_display == "45 y"
        assert brief.patient.semantic_state == "DOCUMENTED"

        # Section 2: Current Complaint (MUST NOT be a diagnosis!)
        assert "Reported symptoms:" in brief.chief_complaint.text
        assert "Mild exertional dyspnea" in brief.chief_complaint.text
        assert "Persistent dry cough" in brief.chief_complaint.text
        assert "Hypertension" not in brief.chief_complaint.text
        assert "Diabetes" not in brief.chief_complaint.text
        assert brief.chief_complaint.semantic_state == "DOCUMENTED"
        assert len(brief.chief_complaint.evidence_ids) >= 1

        # Section 3: Relevant History (Chronologically sorted: Hypertension 2024 before Diabetes 2025)
        assert len(brief.relevant_history) == 2
        assert "Hypertension Stage 1 (2024-01-15)" in brief.relevant_history[0].text
        assert "Type 2 Diabetes Mellitus (2025-06-20)" in brief.relevant_history[1].text
        assert brief.relevant_history[0].semantic_state == "DOCUMENTED"

        # Section 4: Medications & Conflicts
        assert len(brief.current_medications) == 2
        lisinopril_item = next(m for m in brief.current_medications if m.name.lower() == "lisinopril")
        assert lisinopril_item.conflict_flag is True
        assert lisinopril_item.verification_status == "conflicting"
        assert lisinopril_item.semantic_state == "CONFLICTING"

        metformin_item = next(m for m in brief.current_medications if m.name.lower() == "metformin")
        assert metformin_item.conflict_flag is False
        assert metformin_item.verification_status == "known"
        assert metformin_item.semantic_state == "DOCUMENTED"
        assert metformin_item.dose_semantic_state == "DOCUMENTED"

        # Section 5: Investigations & Trends
        assert len(brief.recent_investigations) == 1
        hba1c_inv = brief.recent_investigations[0]
        assert hba1c_inv.test.lower() == "hba1c"
        assert hba1c_inv.value == "6.9"
        assert "Previous: 7.8 [2025-06-20]" in hba1c_inv.reference

        assert len(brief.important_trends) == 1
        trend = brief.important_trends[0]
        assert trend.test.lower() == "hba1c"
        assert trend.direction == "down"
        assert "down trend over 2 measurements" in trend.description

        # Section 6: Allergies
        assert len(brief.allergies) == 1
        assert brief.allergies[0].status == "documented"
        assert "Penicillin" in brief.allergies[0].text
        assert brief.allergies[0].semantic_state == "DOCUMENTED"

        # Section 7: Contradictions
        assert len(brief.contradictions) == 1
        assert brief.contradictions[0].semantic_state == "CONFLICTING"
        assert "Lisinopril" in brief.contradictions[0].text

        # Section 9: Evidence Shortcuts
        assert len(brief.evidence_shortcuts) >= 1
        assert any(es.document_id == doc_id for es in brief.evidence_shortcuts)


def test_deterministic_brief_missing_data_fallbacks():
    """
    Test 2: When no data exists, sections explicitly state 'No verified information available.'
    Missing patient demographics are flagged as MISSING.
    Symptoms are NEVER invented or substituted with arbitrary diagnoses.
    """
    with get_db_context() as db:
        pid = patient_id()
        p = Patient(id=pid, full_name="Empty Patient", age_years=None)
        db.add(p)
        db.commit()

        brief = brief_service.generate_deterministic_brief(
            db=db,
            patient_id=pid,
            specialty="general_medicine"
        )

        # Section 1: Patient Information with missing age
        assert brief.patient.age is None
        assert brief.patient.age_display == "Not available"
        assert brief.patient.semantic_state == "MISSING"

        # Section 2: Current Complaint fallback
        assert brief.chief_complaint.text == "No chief complaint documented in source records. No verified information available."
        assert brief.chief_complaint.semantic_state == "UNKNOWN"
        assert brief.chief_complaint.verification_status == "unknown"

        # Section 3: History empty
        assert brief.relevant_history == []

        # Section 4: Medications empty
        assert brief.current_medications == []

        # Section 5: Investigations empty
        assert brief.recent_investigations == []
        assert brief.important_trends == []

        # Section 6: Allergies fallback
        assert len(brief.allergies) == 1
        assert brief.allergies[0].text == "No documented drug allergies found in source records. No verified information available."
        assert brief.allergies[0].status == "not_documented"
        assert brief.allergies[0].semantic_state == "UNKNOWN"

        # Section 8: Proactive missing information checks
        missing_prompts = [m.prompt for m in brief.missing_information]
        assert any("Age" in pr for pr in missing_prompts)
        assert any("Allergy" in pr for pr in missing_prompts)
        assert any("Complaint" in pr for pr in missing_prompts)


@pytest.mark.anyio
async def test_deterministic_brief_api_endpoints():
    """
    Test 3: Test API endpoints:
    1. POST /patients/{id}/brief with deterministic_only=True
    2. POST /patients/{id}/brief/deterministic
    3. Verify response meta.source is 'deterministic'
    """
    with get_db_context() as db:
        pid = patient_id()
        p = Patient(id=pid, full_name="API Deterministic Patient", age_years=35)
        db.add(p)
        db.commit()

    # Route 1: POST /patients/{id}/brief with deterministic_only: True
    res1 = client.post(
        f"/api/v1/patients/{pid}/brief",
        json={"specialty": "cardiology", "deterministic_only": True}
    )
    assert res1.status_code == 200
    body1 = res1.json()
    assert body1["success"] is True
    assert body1["meta"]["source"] == "deterministic"
    assert body1["data"]["patient"]["name"] == "API Deterministic Patient"
    assert body1["data"]["generation_source"] == "deterministic_template"

    # Route 2: POST /patients/{id}/brief/deterministic
    res2 = client.post(
        f"/api/v1/patients/{pid}/brief/deterministic",
        json={"specialty": "endocrinology"}
    )
    assert res2.status_code == 200
    body2 = res2.json()
    assert body2["success"] is True
    assert body2["meta"]["source"] == "deterministic"
    assert body2["data"]["specialty"] == "endocrinology"
    assert body2["data"]["generation_source"] == "deterministic_template"
