import datetime
import pytest
from sqlalchemy.orm import Session

from app.db.database import get_db_context
from app.models.patient import Patient
from app.models.document import Document
from app.models.clinical_fact import ClinicalFact
from app.models.investigation import Investigation
from app.models.medication import Medication
from app.models.contradiction import Contradiction
from app.utils.ids import patient_id, document_id, fact_id, investigation_id, medication_id
from app.schemas.contradiction import DifferenceClassification, ContradictionLifecycle
from app.services.difference_evaluator import difference_evaluator
from app.services.contradiction_service import contradiction_service


@pytest.fixture
def make_patient():
    def _create(db: Session, name: str = "Contradiction Test Patient") -> Patient:
        p = Patient(id=patient_id(), full_name=name)
        db.add(p)
        db.flush()
        return p
    return _create


@pytest.fixture
def make_doc():
    def _create(db: Session, pid: str, filename: str, doc_date: datetime.datetime = None, doc_type: str = "lab_report") -> Document:
        doc = Document(
            id=document_id(),
            patient_id=pid,
            original_filename=filename,
            stored_path=f"storage/{filename}",
            mime_type="application/pdf",
            document_type=doc_type,
            file_size=1024,
            sha256=f"sha_{filename}",
            document_date=doc_date,
            processing_status="complete"
        )
        db.add(doc)
        db.flush()
        return doc
    return _create


def test_evaluator_lab_trend_across_different_dates():
    """
    HbA1c = 7.1 on January 1 vs HbA1c = 8.2 on June 1.
    Must be classified as TREND, NOT a contradiction.
    """
    res = difference_evaluator.evaluate_investigation_difference(
        entity="HbA1c",
        val_a=7.1,
        val_b=8.2,
        unit_a="%",
        unit_b="%",
        date_a=datetime.datetime(2026, 1, 1),
        date_b=datetime.datetime(2026, 6, 1),
        doc_a_meta={"filename": "lab_jan.pdf"},
        doc_b_meta={"filename": "lab_jun.pdf"},
    )
    assert res.classification == DifferenceClassification.TREND
    assert res.is_contradiction is False
    assert "trend" in res.reason.lower()
    assert res.conflicting_values["source_a"] == "7.1 %"
    assert res.conflicting_values["source_b"] == "8.2 %"


def test_evaluator_lab_contradiction_on_same_date():
    """
    Two documents dated June 1:
    HbA1c = 7.1 vs HbA1c = 8.2 on June 1.
    Must be classified as CONTRADICTION.
    """
    res = difference_evaluator.evaluate_investigation_difference(
        entity="HbA1c",
        val_a=7.1,
        val_b=8.2,
        unit_a="%",
        unit_b="%",
        date_a=datetime.datetime(2026, 6, 1),
        date_b=datetime.datetime(2026, 6, 1),
        doc_a_meta={"filename": "lab_morning.pdf"},
        doc_b_meta={"filename": "lab_evening.pdf"},
        evidence_a={"source_text": "HbA1c 7.1%", "source_page": 1},
        evidence_b={"source_text": "HbA1c 8.2%", "source_page": 2},
    )
    assert res.classification == DifferenceClassification.CONTRADICTION
    assert res.is_contradiction is True
    assert "conflicting" in res.reason.lower()
    assert res.conflicting_values["source_a"] == "7.1 %"
    assert res.conflicting_values["source_b"] == "8.2 %"
    assert res.dates["source_a_date"] == "2026-06-01"
    assert res.dates["source_b_date"] == "2026-06-01"
    assert res.evidence_spans["source_a"]["source_text"] == "HbA1c 7.1%"
    assert res.evidence_spans["source_b"]["source_text"] == "HbA1c 8.2%"


def test_evaluator_medication_change_vs_same_date_contradiction():
    """
    Medication across different dates -> CHANGE.
    Medication on same date with differing doses -> CONTRADICTION.
    """
    # 1. Distinct dates: Metformin 500mg in Jan vs 1000mg in Mar -> CHANGE
    res_change = difference_evaluator.evaluate_medication_difference(
        entity="Metformin",
        dose_a="500mg",
        dose_b="1000mg",
        freq_a="once daily",
        freq_b="once daily",
        date_a=datetime.datetime(2026, 1, 10),
        date_b=datetime.datetime(2026, 3, 10),
    )
    assert res_change.classification == DifferenceClassification.CHANGE
    assert res_change.is_contradiction is False

    # 2. Same date: Metformin 500mg OD vs 1000mg BD on same date -> CONTRADICTION
    res_conflict = difference_evaluator.evaluate_medication_difference(
        entity="Metformin",
        dose_a="500mg",
        dose_b="1000mg",
        freq_a="once daily",
        freq_b="twice daily",
        date_a=datetime.datetime(2026, 9, 20),
        date_b=datetime.datetime(2026, 9, 20),
        doc_a_meta={"filename": "clinic.pdf"},
        doc_b_meta={"filename": "hospital.pdf"},
    )
    assert res_conflict.classification == DifferenceClassification.CONTRADICTION
    assert res_conflict.is_contradiction is True


def test_evaluator_duplicate_and_supersession_and_ambiguous():
    """
    Test DUPLICATE, SUPERSESSION, and AMBIGUOUS classifications.
    """
    # Duplicate lab
    res_dup = difference_evaluator.evaluate_investigation_difference(
        entity="Potassium",
        val_a=4.2,
        val_b=4.2,
        unit_a="mmol/L",
        unit_b="mmol/L",
        date_a=datetime.datetime(2026, 5, 1),
        date_b=datetime.datetime(2026, 5, 1),
    )
    assert res_dup.classification == DifferenceClassification.DUPLICATE
    assert res_dup.is_contradiction is False

    # Superseded medication (stopped on later visit)
    res_super = difference_evaluator.evaluate_medication_difference(
        entity="Lisinopril",
        dose_a="10mg",
        dose_b="10mg",
        freq_a="OD",
        freq_b="OD",
        status_a="current",
        status_b="previous",
        date_a=datetime.datetime(2026, 1, 1),
        date_b=datetime.datetime(2026, 3, 1),
    )
    assert res_super.classification == DifferenceClassification.SUPERSESSION
    assert res_super.is_contradiction is False

    # Low confidence extraction -> AMBIGUOUS
    res_amb = difference_evaluator.evaluate_investigation_difference(
        entity="Creatinine",
        val_a=1.1,
        val_b=1.8,
        conf_a=0.50,
        conf_b=0.95,
        date_a=datetime.datetime(2026, 2, 1),
        date_b=datetime.datetime(2026, 2, 1),
    )
    assert res_amb.classification == DifferenceClassification.AMBIGUOUS
    assert res_amb.is_contradiction is False


def test_contradiction_service_recompute_temporal_lab_trend(make_patient, make_doc):
    """
    End-to-end integration:
    Two lab documents on different dates (Jan 1 vs Jun 1).
    ContradictionService.recompute MUST NOT flag them as contradictions.
    """
    with get_db_context() as db:
        p = make_patient(db)
        d1 = make_doc(db, p.id, "lab_jan.pdf", datetime.datetime(2026, 1, 1))
        d2 = make_doc(db, p.id, "lab_jun.pdf", datetime.datetime(2026, 6, 1))

        f1 = ClinicalFact(
            id=fact_id(),
            patient_id=p.id,
            document_id=d1.id,
            fact_type="investigation",
            value="HbA1c 7.1%",
            source_text="HbA1c = 7.1%",
            confidence=0.95,
        )
        f2 = ClinicalFact(
            id=fact_id(),
            patient_id=p.id,
            document_id=d2.id,
            fact_type="investigation",
            value="HbA1c 8.2%",
            source_text="HbA1c = 8.2%",
            confidence=0.95,
        )
        db.add_all([f1, f2])
        db.flush()

        inv1 = Investigation(
            id=investigation_id(),
            patient_id=p.id,
            fact_id=f1.id,
            test_name_raw="HbA1c",
            test_name_canonical="hba1c",
            value_numeric=7.1,
            value_text="7.1",
            unit="%",
            observed_date=datetime.datetime(2026, 1, 1),
            source_document_id=d1.id,
            group_key=f"{p.id}_hba1c",
            confidence=0.95,
        )
        inv2 = Investigation(
            id=investigation_id(),
            patient_id=p.id,
            fact_id=f2.id,
            test_name_raw="HbA1c",
            test_name_canonical="hba1c",
            value_numeric=8.2,
            value_text="8.2",
            unit="%",
            observed_date=datetime.datetime(2026, 6, 1),
            source_document_id=d2.id,
            group_key=f"{p.id}_hba1c",
            confidence=0.95,
        )
        db.add_all([inv1, inv2])
        db.commit()

        # Recompute contradictions
        issues = contradiction_service.recompute(db, p.id)
        # MUST NOT create any lab conflict
        assert not any(i["issue_type"] == "lab_conflict" for i in issues)


def test_contradiction_service_recompute_same_date_lab_conflict(make_patient, make_doc):
    """
    End-to-end integration:
    Two lab documents on the SAME date (June 1) with differing HbA1c values (7.1 vs 8.2).
    ContradictionService.recompute MUST flag it as a lab_conflict CONTRADICTION.
    And verify all 8 required fields: entity, conflicting values, source A, source B, dates, evidence spans, confidence, status.
    """
    with get_db_context() as db:
        p = make_patient(db)
        same_date = datetime.datetime(2026, 6, 1)
        d1 = make_doc(db, p.id, "lab_clinic_morning.pdf", same_date)
        d2 = make_doc(db, p.id, "lab_hospital_evening.pdf", same_date)

        f1 = ClinicalFact(
            id=fact_id(),
            patient_id=p.id,
            document_id=d1.id,
            fact_type="investigation",
            value="HbA1c 7.1%",
            source_text="HbA1c: 7.1% (morning test)",
            source_page=1,
            confidence=0.95,
        )
        f2 = ClinicalFact(
            id=fact_id(),
            patient_id=p.id,
            document_id=d2.id,
            fact_type="investigation",
            value="HbA1c 8.2%",
            source_text="HbA1c: 8.2% (evening test)",
            source_page=2,
            confidence=0.90,
        )
        db.add_all([f1, f2])
        db.flush()

        inv1 = Investigation(
            id=investigation_id(),
            patient_id=p.id,
            fact_id=f1.id,
            test_name_raw="HbA1c",
            test_name_canonical="hba1c",
            value_numeric=7.1,
            value_text="7.1",
            unit="%",
            observed_date=same_date,
            source_document_id=d1.id,
            group_key=f"{p.id}_hba1c",
            confidence=0.95,
        )
        inv2 = Investigation(
            id=investigation_id(),
            patient_id=p.id,
            fact_id=f2.id,
            test_name_raw="HbA1c",
            test_name_canonical="hba1c",
            value_numeric=8.2,
            value_text="8.2",
            unit="%",
            observed_date=same_date,
            source_document_id=d2.id,
            group_key=f"{p.id}_hba1c",
            confidence=0.90,
        )
        db.add_all([inv1, inv2])
        db.commit()

        # Recompute contradictions
        issues = contradiction_service.recompute(db, p.id)
        lab_issues = [i for i in issues if i["issue_type"] == "lab_conflict"]
        assert len(lab_issues) == 1

        # Fetch detailed patient issues
        patient_issues = contradiction_service.get_patient_issues(db, p.id, issue_type="lab_conflict")
        assert len(patient_issues) == 1
        iss = patient_issues[0]

        # Verify all 8 mandated fields
        assert iss["entity"] == "HbA1c"
        assert iss["conflicting_values"]["source_a"] == "7.1 %"
        assert iss["conflicting_values"]["source_b"] == "8.2 %"
        assert iss["source_a"]["filename"] == "lab_clinic_morning.pdf"
        assert iss["source_b"]["filename"] == "lab_hospital_evening.pdf"
        assert iss["dates"]["source_a_date"] == "2026-06-01"
        assert iss["dates"]["source_b_date"] == "2026-06-01"
        assert iss["evidence_spans"]["source_a"]["source_text"] == "HbA1c: 7.1% (morning test)"
        assert iss["evidence_spans"]["source_b"]["source_text"] == "HbA1c: 8.2% (evening test)"
        assert iss["confidence"] == 0.90
        assert iss["lifecycle_status"] == ContradictionLifecycle.DETECTED.value
        assert iss["status"] == "open"


def test_contradiction_lifecycle_transitions(make_patient, make_doc):
    """
    Test Contradiction lifecycle:
    DETECTED -> PRESENTED TO DOCTOR -> DOCTOR RESOLVES -> RESOLVED
    Never silently discard one conflicting value.
    """
    with get_db_context() as db:
        p = make_patient(db)
        same_date = datetime.datetime(2026, 6, 1)
        d1 = make_doc(db, p.id, "lab_a.pdf", same_date)
        d2 = make_doc(db, p.id, "lab_b.pdf", same_date)

        f1 = ClinicalFact(id=fact_id(), patient_id=p.id, document_id=d1.id, fact_type="investigation", value="7.1", source_text="HbA1c 7.1%")
        f2 = ClinicalFact(id=fact_id(), patient_id=p.id, document_id=d2.id, fact_type="investigation", value="8.2", source_text="HbA1c 8.2%")
        db.add_all([f1, f2])
        db.flush()

        inv1 = Investigation(id=investigation_id(), patient_id=p.id, fact_id=f1.id, test_name_raw="HbA1c", test_name_canonical="hba1c", value_numeric=7.1, value_text="7.1", observed_date=same_date, source_document_id=d1.id, group_key=f"{p.id}_hba1c")
        inv2 = Investigation(id=investigation_id(), patient_id=p.id, fact_id=f2.id, test_name_raw="HbA1c", test_name_canonical="hba1c", value_numeric=8.2, value_text="8.2", observed_date=same_date, source_document_id=d2.id, group_key=f"{p.id}_hba1c")
        db.add_all([inv1, inv2])
        db.commit()

        # 1. DETECTED
        issues = contradiction_service.recompute(db, p.id)
        assert len(issues) == 1
        iss_id = issues[0]["id"]

        detail = contradiction_service.get_patient_issues(db, p.id)[0]
        assert detail["lifecycle_status"] == "DETECTED"

        # 2. PRESENTED TO DOCTOR
        p_res = contradiction_service.patch_issue(db, iss_id, status="PRESENTED TO DOCTOR")
        assert p_res["lifecycle_status"] == "PRESENTED TO DOCTOR"
        assert p_res["status"] in ("presented", "PRESENTED TO DOCTOR")

        # 3. DOCTOR RESOLVES
        dr_res = contradiction_service.patch_issue(db, iss_id, status="DOCTOR RESOLVES", doctor_note="Repeat lab ordered due to sampling artifact")
        assert dr_res["lifecycle_status"] == "DOCTOR RESOLVES"
        assert dr_res["status"] in ("acknowledged", "DOCTOR RESOLVES")
        assert dr_res["doctor_note"] == "Repeat lab ordered due to sampling artifact"

        # 4. RESOLVED
        res_res = contradiction_service.patch_issue(db, iss_id, status="RESOLVED", doctor_note="Resolved: Morning sample confirmed erroneous")
        assert res_res["lifecycle_status"] == "RESOLVED"
        assert res_res["status"] in ("resolved", "resolved_by_doctor", "RESOLVED")

        # Verify neither value was discarded throughout lifecycle
        assert res_res["conflicting_values"]["source_a"]
        assert res_res["conflicting_values"]["source_b"]
        assert res_res["source_a"]["filename"] == "lab_a.pdf"
        assert res_res["source_b"]["filename"] == "lab_b.pdf"
