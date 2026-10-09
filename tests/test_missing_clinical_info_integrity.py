import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_db_context
from app.models.patient import Patient
from app.models.document import Document
from app.models.clinical_fact import ClinicalFact
from app.models.medication import Medication
from app.models.investigation import Investigation
from app.models.contradiction import Contradiction
from app.models.consultation import Consultation, ConsultationVersion
from app.models.clinical_memory import ClinicalMemory
from app.models.timeline_event import TimelineEvent
from app.models.user import User
from app.utils.ids import (
    patient_id, fact_id, medication_id, investigation_id,
    contradiction_id, consultation_id, version_id, document_id
)
from app.services.brief_service import brief_service
from app.services.extraction_service import extraction_service
from app.services.normalization_service import normalization_service
from app.services.consultation_service import consultation_service
from app.schemas.ai_contracts import ExtractionMedication, ExtractionResult, EvidenceReference
from app.schemas.brief import DoctorBrief

client = TestClient(app)


def test_missing_age_is_preserved_as_none_and_not_defaulted_to_45():
    """Missing patient age must remain None / null, never defaulted to 45."""
    with get_db_context() as db:
        pid = patient_id()
        p = Patient(id=pid, full_name="Ageless Patient", age_years=None)
        db.add(p)
        db.commit()

        # Deterministic brief generation
        brief = brief_service._build_deterministic_template_brief(
            patient=p,
            specialty="general_medicine",
            facts=[],
            meds=[],
            invs=[],
            issues=[]
        )
        assert brief.patient.age is None
        assert brief.patient.age_display == "Not available"
        assert brief.patient.age != 45

        # Check serialization
        serialized = brief.model_dump()
        assert serialized["patient"]["age"] is None
        assert serialized["patient"]["age_display"] == "Not available"


def test_missing_allergies_has_empty_evidence_and_unknown_status():
    """
    When no allergies are documented, evidence_ids must be empty and verification_status
    must be 'unknown'. Never cite unrelated clinical facts as evidence for missing allergies.
    """
    with get_db_context() as db:
        pid = patient_id()
        p = Patient(id=pid, full_name="Allergy Test Patient", age_years=40)
        db.add(p)
        db.flush()

        # Add an unrelated lab fact
        f_lab = ClinicalFact(
            id=fact_id(),
            patient_id=pid,
            fact_type="investigation",
            value="HbA1c 6.2%",
            source_text="HbA1c 6.2%",
            provenance_verified=True,
            confidence=0.9
        )
        db.add(f_lab)
        db.commit()

        brief = brief_service._build_deterministic_template_brief(
            patient=p,
            specialty="general_medicine",
            facts=[f_lab],
            meds=[],
            invs=[],
            issues=[]
        )

        assert len(brief.allergies) == 1
        alg = brief.allergies[0]
        assert alg.status == "not_documented"
        assert alg.verification_status == "unknown"
        # Crucial: Must NOT attach f_lab.id as evidence for allergy status
        assert alg.evidence_ids == []
        assert f_lab.id not in alg.evidence_ids


def test_missing_chief_complaint_and_symptoms_marked_unknown():
    """
    When records lack both diagnoses and symptoms, chief complaint must reflect
    lack of documentation, not fabricate a clinical complaint or assume high confidence.
    """
    with get_db_context() as db:
        pid = patient_id()
        p = Patient(id=pid, full_name="Quiet Patient", age_years=35)
        db.add(p)
        db.commit()

        brief = brief_service._build_deterministic_template_brief(
            patient=p,
            specialty="general_medicine",
            facts=[],
            meds=[],
            invs=[],
            issues=[]
        )

        cc = brief.chief_complaint
        assert "No chief complaint documented" in cc.text
        assert cc.evidence_ids == []
        assert cc.verification_status == "unknown"
        assert cc.confidence_band == "low"


def test_conflicting_medication_flag_and_status():
    """
    Medications with documented discrepancies must be marked conflict_flag=True
    and verification_status='conflicting'. Non-conflicting meds must be flagged False.
    """
    with get_db_context() as db:
        pid = patient_id()
        p = Patient(id=pid, full_name="Conflict Patient", age_years=60)
        db.add(p)
        db.flush()

        f_met = ClinicalFact(
            id=fact_id(),
            patient_id=pid,
            fact_type="medication",
            value="Metformin 500mg",
            source_text="Metformin 500mg",
            provenance_verified=True,
            confidence=0.9
        )
        f_atorva = ClinicalFact(
            id=fact_id(),
            patient_id=pid,
            fact_type="medication",
            value="Atorvastatin 20mg",
            source_text="Atorvastatin 20mg",
            provenance_verified=True,
            confidence=0.9
        )
        db.add_all([f_met, f_atorva])
        db.flush()

        m_metformin = Medication(
            id=medication_id(),
            patient_id=pid,
            fact_id=f_met.id,
            canonical_name="metformin",
            raw_name="Metformin 500mg",
            strength_value=500.0,
            strength_unit="mg",
            status="current",
            group_key=f"{pid}_metformin",
            confidence=0.9
        )
        m_atorva = Medication(
            id=medication_id(),
            patient_id=pid,
            fact_id=f_atorva.id,
            canonical_name="atorvastatin",
            raw_name="Atorvastatin 20mg",
            strength_value=20.0,
            strength_unit="mg",
            status="current",
            group_key=f"{pid}_atorvastatin",
            confidence=0.9
        )
        issue = Contradiction(
            id=contradiction_id(),
            patient_id=pid,
            issue_type="medication_conflict",
            title="Dosing conflict on Metformin",
            description="Metformin dosage differs between discharge summary (1000mg) and prescription (500mg)",
            severity="high",
            status="open"
        )
        db.add_all([m_metformin, m_atorva, issue])
        db.commit()

        brief = brief_service._build_deterministic_template_brief(
            patient=p,
            specialty="general_medicine",
            facts=[f_met, f_atorva],
            meds=[m_metformin, m_atorva],
            invs=[],
            issues=[issue]
        )

        met_item = next(m for m in brief.current_medications if m.name.lower() == "metformin")
        atorva_item = next(m for m in brief.current_medications if m.name.lower() == "atorvastatin")

        assert met_item.conflict_flag is True
        assert met_item.verification_status == "conflicting"

        assert atorva_item.conflict_flag is False
        assert atorva_item.verification_status != "conflicting"


def test_deterministic_extraction_never_fabricates_lab_reference_range_or_flag():
    """
    Deterministic extraction fallback must not supply population-average reference ranges
    ('< 5.7%') or flags ('normal') when omitted from the source text.
    """
    # 1. Text with NO reference range
    pages_no_ref = [{"page_number": 1, "text": "Lab Results: HbA1c 6.1%"}]
    result_no_ref = extraction_service._fallback_deterministic_extract(pages_no_ref)
    assert len(result_no_ref.investigations) == 1
    inv1 = result_no_ref.investigations[0]
    assert inv1.value == "6.1"
    assert inv1.reference_range is None
    assert inv1.flag is None

    # 2. Text with explicit reference range
    pages_with_ref = [{"page_number": 1, "text": "Lab Results: HbA1c 6.1% (ref: < 5.7%) abnormal high"}]
    result_with_ref = extraction_service._fallback_deterministic_extract(pages_with_ref)
    assert len(result_with_ref.investigations) == 1
    inv2 = result_with_ref.investigations[0]
    assert inv2.value == "6.1"
    assert inv2.reference_range == "< 5.7%"
    assert inv2.flag in ["high", "abnormal"]


def test_undated_document_timeline_events_have_null_event_date():
    """
    Undated documents must create timeline events with event_date=None and
    date_precision='unknown', never defaulting to datetime.now().
    """
    with get_db_context() as db:
        pid = patient_id()
        p = Patient(id=pid, full_name="Undated Patient", age_years=50)
        db.add(p)
        db.flush()

        doc = Document(
            id=document_id(),
            patient_id=pid,
            original_filename="Undated Prescription.pdf",
            stored_path="dummy.pdf",
            mime_type="application/pdf",
            sha256="dummy_checksum_12345",
            file_size=1024,
            document_date=None,  # No date
            processing_status="completed"
        )
        db.add(doc)
        db.flush()

        # Simulate adding a medication via pipeline orchestrator logic
        evt = TimelineEvent(
            patient_id=pid,
            event_type="medication_start",
            event_date=doc.document_date if doc.document_date else None,
            date_precision="day" if doc.document_date else "unknown",
            title="Started Metformin",
            summary="Metformin 500mg OD",
            sort_key="9999-99-99"
        )
        db.add(evt)
        db.commit()

        saved_evt = db.query(TimelineEvent).filter(TimelineEvent.patient_id == pid).first()
        assert saved_evt is not None
        assert saved_evt.event_date is None
        assert saved_evt.date_precision == "unknown"


def test_consultation_approval_to_clinical_memory_never_synthesizes_missing_fields(monkeypatch):
    """
    When a doctor approves a consultation note that only has a chief complaint,
    only that item is written to clinical_memory. Missing assessment/plan must NOT be synthesized.
    """
    monkeypatch.setattr(
        "app.validation.gate1_memory.evaluate_gate1_judge",
        lambda **kw: (True, "info", {"passed": True, "verdict": "faithful"}),
    )
    with get_db_context() as db:
        pid = patient_id()
        p = Patient(id=pid, full_name="Memory Audit Patient", age_years=48)
        db.add(p)
        db.flush()

        cid = consultation_id()
        vid = version_id()
        cns = Consultation(
            id=cid,
            patient_id=pid,
            status="draft",
            current_version_id=vid
        )
        ver = ConsultationVersion(
            id=vid,
            consultation_id=cid,
            version_number=1,
            origin="doctor_edited",  # edited by doctor, passes Gate 1
            edited_by="doc_audit_1",
            content_json='{"chief_complaint": "Persistent cough for 2 weeks"}'
        )
        user = User(
            id="doc_audit_1",
            email="doc_audit_1@example.com",
            full_name="Dr. Audit",
            role="admin",
            hashed_password="pw",
            is_active=True
        )
        db.add_all([user, cns, ver])
        db.commit()

        # Approve consultation
        res = consultation_service.approve(
            db=db,
            cid=cid,
            approved_by="doc_audit_1"
        )
        assert res["status"] == "approved"

        # Check clinical memory entries
        memories = db.query(ClinicalMemory).filter(ClinicalMemory.patient_id == pid).all()
        assert len(memories) == 1
        assert memories[0].memory_type == "diagnosis"
        # Ensure no assessment or plan memory was fabricated
        types = [m.memory_type for m in memories]
        assert "assessment" not in types
        assert "plan_note" not in types


def test_end_to_end_missing_clinical_info_pipeline(monkeypatch):
    """
    Validates end-to-end that missing clinical fields remain missing and un-fabricated
    across every layer: document -> extraction -> normalization -> database -> brief -> clinical memory.
    """
    monkeypatch.setattr(
        "app.validation.gate1_memory.evaluate_gate1_judge",
        lambda **kw: (True, "info", {"passed": True, "verdict": "faithful"}),
    )

    # 1. Document layer: Raw input text lacks dose, frequency, date, allergies, and age
    raw_document_text = "Patient seen for routine consultation. Currently taking Metformin. No known allergies stated."
    pages = [{"page_number": 1, "text": raw_document_text}]

    # 2. Extraction layer: Extraction preserves missing values as None
    extraction = extraction_service._fallback_deterministic_extract(pages)
    assert len(extraction.medications) >= 1
    ext_med = next(m for m in extraction.medications if m.name.lower() == "metformin")
    # Dose and frequency are not in text, so must remain None (never guessed)
    assert ext_med.dose is None
    assert ext_med.frequency is None
    assert ext_med.strength is None

    # 3. Normalization layer: Normalization maintains None for missing fields
    norm_med = normalization_service.normalize_medication(
        raw_name=ext_med.name,
        raw_strength=ext_med.strength,
        raw_frequency=ext_med.frequency
    )
    assert norm_med["canonical_name"] == "metformin"
    assert norm_med["strength_value"] is None
    assert norm_med["strength_unit"] is None
    assert norm_med["frequency_text"] is None
    assert norm_med["start_date"] is None
    assert norm_med["stop_date"] is None

    # 4. Database layer: DB records persist None / NULL without placeholder values
    with get_db_context() as db:
        pid = patient_id()
        p = Patient(id=pid, full_name="End-to-End Pipeline Patient", age_years=None)
        db.add(p)
        db.flush()

        doc_row = Document(
            id=document_id(),
            patient_id=pid,
            original_filename="record.pdf",
            stored_path="record.pdf",
            mime_type="application/pdf",
            sha256="pipeline_doc_sha256",
            file_size=2048,
            document_date=None,  # Undated
            processing_status="completed"
        )
        db.add(doc_row)
        db.flush()

        f_med = ClinicalFact(
            id=fact_id(),
            patient_id=pid,
            document_id=doc_row.id,
            fact_type="medication",
            value=f"{norm_med['canonical_name']} {norm_med['strength_value'] or ''}".strip(),
            source_text=ext_med.evidence.text,
            source_page=ext_med.evidence.page,
            fact_date=doc_row.document_date,
            provenance_verified=True,
            confidence=0.85
        )
        db.add(f_med)
        db.flush()

        db_med = Medication(
            id=medication_id(),
            patient_id=pid,
            fact_id=f_med.id,
            canonical_name=norm_med["canonical_name"],
            raw_name=ext_med.name,
            strength_value=norm_med["strength_value"],
            strength_unit=norm_med["strength_unit"],
            dose_text=None,
            frequency_text=None,
            frequency_code="other",
            status="current",
            group_key=f"{pid}_metformin",
            confidence=0.85
        )
        db.add(db_med)

        # Timeline event for undated document
        tl_evt = TimelineEvent(
            patient_id=pid,
            event_type="medication_start",
            event_date=doc_row.document_date if doc_row.document_date else None,
            date_precision="day" if doc_row.document_date else "unknown",
            title="Started Metformin",
            summary="Metformin (dose unrecorded)",
            sort_key="9999-99-99"
        )
        db.add(tl_evt)
        db.commit()

        # Verify DB values are strictly None/NULL
        saved_db_med = db.query(Medication).filter(Medication.patient_id == pid).first()
        assert saved_db_med.strength_value is None
        assert saved_db_med.dose_text is None
        assert saved_db_med.start_date is None

        saved_db_evt = db.query(TimelineEvent).filter(TimelineEvent.patient_id == pid).first()
        assert saved_db_evt.event_date is None
        assert saved_db_evt.date_precision == "unknown"

        # 5. Brief layer: Generated DoctorBrief reflects missing fields truthfully
        brief = brief_service._build_deterministic_template_brief(
            patient=p,
            specialty="general_medicine",
            facts=[f_med],
            meds=[db_med],
            invs=[],
            issues=[]
        )
        # Age
        assert brief.patient.age is None
        assert brief.patient.age_display == "Not available"
        # Medication dose / strength / frequency
        brief_med = brief.current_medications[0]
        assert brief_med.name == "Metformin"
        assert brief_med.strength == ""
        assert brief_med.dose == ""
        assert brief_med.frequency == ""
        # Allergies
        assert len(brief.allergies) == 1
        assert brief.allergies[0].status == "not_documented"
        assert brief.allergies[0].verification_status == "unknown"
        assert brief.allergies[0].evidence_ids == []
        # Chief complaint
        assert brief.chief_complaint.verification_status == "unknown"

        # 6. Clinical Memory layer: Doctor approval creates memory ONLY for documented facts
        cid = consultation_id()
        vid = version_id()
        cns = Consultation(id=cid, patient_id=pid, status="draft", current_version_id=vid)
        ver = ConsultationVersion(
            id=vid,
            consultation_id=cid,
            version_number=1,
            origin="doctor_edited",
            edited_by="admin_pipeline_user",
            # Note only documents chief complaint; does NOT document assessment or plan
            content_json='{"chief_complaint": "Follow up on Metformin tolerance"}'
        )
        admin_user = User(
            id="admin_pipeline_user",
            email="admin_pipeline@example.com",
            full_name="Admin Pipeline Doctor",
            role="admin",
            hashed_password="pw",
            is_active=True
        )
        db.add_all([cns, ver, admin_user])
        db.commit()

        appr_res = consultation_service.approve(db=db, cid=cid, approved_by="admin_pipeline_user")
        assert appr_res["status"] == "approved"

        # ClinicalMemory contains only the documented item; missing fields never synthesized
        memories = db.query(ClinicalMemory).filter(ClinicalMemory.patient_id == pid).all()
        assert len(memories) == 1
        assert memories[0].memory_type == "diagnosis"
        mem_types = [m.memory_type for m in memories]
        assert "assessment" not in mem_types
        assert "plan_note" not in mem_types

