import datetime
import pytest
from sqlalchemy.orm import Session

from app.db.database import get_db_context
from app.models.patient import Patient
from app.models.document import Document
from app.models.clinical_fact import ClinicalFact
from app.models.medication import Medication
from app.models.contradiction import Contradiction
from app.utils.ids import patient_id, document_id, fact_id, medication_id
from app.schemas.medication import ReconciliationChangeType
from app.services.medication_service import medication_service
from app.services.contradiction_service import contradiction_service


@pytest.fixture
def make_patient():
    def _create(db: Session, name: str = "Reconciliation Test Patient") -> Patient:
        p = Patient(id=patient_id(), full_name=name)
        db.add(p)
        db.flush()
        return p
    return _create


@pytest.fixture
def make_doc():
    def _create(db: Session, pid: str, filename: str, doc_date: datetime.datetime = None) -> Document:
        doc = Document(
            id=document_id(),
            patient_id=pid,
            original_filename=filename,
            stored_path=f"storage/{filename}",
            mime_type="application/pdf",
            file_size=1024,
            sha256=f"sha_{filename}",
            document_date=doc_date,
            processing_status="complete"
        )
        db.add(doc)
        db.flush()
        return doc
    return _create


@pytest.fixture
def make_fact():
    def _create(
        db: Session,
        pid: str,
        doc_id: str,
        value: str,
        source_text: str,
        source_page: int = 1,
        fact_date: datetime.datetime = None
    ) -> ClinicalFact:
        fact = ClinicalFact(
            id=fact_id(),
            patient_id=pid,
            document_id=doc_id,
            fact_type="medication",
            value=value,
            source_text=source_text,
            source_page=source_page,
            provenance_verified=True,
            confidence=0.95,
            fact_date=fact_date,
        )
        db.add(fact)
        db.flush()
        return fact
    return _create


def test_scenario_1_same_medication_same_dose_continued(make_patient, make_doc, make_fact):
    """
    Scenario 1: Same medication, same dose across visits -> CONTINUED.
    No contradiction emitted.
    """
    with get_db_context() as db:
        p = make_patient(db)
        d1 = make_doc(db, p.id, "visit_jan.pdf", datetime.datetime(2026, 1, 10))
        d2 = make_doc(db, p.id, "visit_mar.pdf", datetime.datetime(2026, 3, 10))

        f1 = make_fact(db, p.id, d1.id, "Metformin 500mg OD", "Tab Metformin 500mg OD")
        f2 = make_fact(db, p.id, d2.id, "Metformin 500mg OD", "Tab Metformin 500mg OD")

        m1 = Medication(
            id=medication_id(),
            patient_id=p.id,
            fact_id=f1.id,
            canonical_name="metformin",
            raw_name="Metformin",
            strength_value=500.0,
            strength_unit="mg",
            dose_text="500mg",
            frequency_code="OD",
            frequency_text="once daily",
            route="oral",
            status="current",
            group_key=f"{p.id}_metformin",
            source_document_id=d1.id,
        )
        m2 = Medication(
            id=medication_id(),
            patient_id=p.id,
            fact_id=f2.id,
            canonical_name="metformin",
            raw_name="Metformin",
            strength_value=500.0,
            strength_unit="mg",
            dose_text="500mg",
            frequency_code="OD",
            frequency_text="once daily",
            route="oral",
            status="current",
            group_key=f"{p.id}_metformin",
            source_document_id=d2.id,
        )
        db.add_all([m1, m2])
        db.commit()

        timelines = medication_service.reconcile_patient_medications(db, p.id)
        assert len(timelines) == 1
        tl = timelines[0]
        assert tl["canonical_name"] == "metformin"
        assert tl["current_status"] == "current"
        assert tl["has_conflict"] is False
        assert len(tl["history"]) == 2

        assert tl["history"][0]["change_type"] == ReconciliationChangeType.NEW_MEDICATION.value
        assert tl["history"][1]["change_type"] == ReconciliationChangeType.CONTINUED.value
        assert "continued" in tl["history"][1]["change_description"].lower()

        # Contradiction service should not find conflicts
        issues = contradiction_service.recompute(db, p.id)
        assert not any(i["issue_type"] == "medication_conflict" for i in issues)


def test_scenario_2_same_medication_changed_dose(make_patient, make_doc, make_fact):
    """
    Scenario 2: Same medication, changed dose across visits -> DOSE_CHANGE.
    Chronologically explainable: January 500mg -> March 1000mg.
    Must NOT be treated as a contradiction!
    """
    with get_db_context() as db:
        p = make_patient(db)
        d1 = make_doc(db, p.id, "visit_jan.pdf", datetime.datetime(2026, 1, 10))
        d2 = make_doc(db, p.id, "visit_mar.pdf", datetime.datetime(2026, 3, 10))

        f1 = make_fact(db, p.id, d1.id, "Metformin 500mg OD", "Tab Metformin 500mg OD")
        f2 = make_fact(db, p.id, d2.id, "Metformin 1000mg OD", "Tab Metformin 1000mg OD")

        m1 = Medication(
            id=medication_id(),
            patient_id=p.id,
            fact_id=f1.id,
            canonical_name="metformin",
            raw_name="Metformin",
            strength_value=500.0,
            strength_unit="mg",
            dose_text="500mg",
            frequency_code="OD",
            frequency_text="once daily",
            route="oral",
            status="current",
            group_key=f"{p.id}_metformin",
            source_document_id=d1.id,
        )
        m2 = Medication(
            id=medication_id(),
            patient_id=p.id,
            fact_id=f2.id,
            canonical_name="metformin",
            raw_name="Metformin",
            strength_value=1000.0,
            strength_unit="mg",
            dose_text="1000mg",
            frequency_code="OD",
            frequency_text="once daily",
            route="oral",
            status="current",
            group_key=f"{p.id}_metformin",
            source_document_id=d2.id,
        )
        db.add_all([m1, m2])
        db.commit()

        timelines = medication_service.reconcile_patient_medications(db, p.id)
        assert len(timelines) == 1
        tl = timelines[0]
        assert tl["has_conflict"] is False
        assert tl["latest_change_type"] == ReconciliationChangeType.DOSE_CHANGE.value
        assert "500" in tl["latest_change_reason"] and "1000" in tl["latest_change_reason"]
        assert tl["current_dose"] == "1000mg"

        # Not a contradiction because it is chronologically ordered
        issues = contradiction_service.recompute(db, p.id)
        assert not any(i["issue_type"] == "medication_conflict" for i in issues)


def test_scenario_3_same_medication_changed_frequency(make_patient, make_doc, make_fact):
    """
    Scenario 3: Same medication, changed frequency across visits -> FREQUENCY_CHANGE.
    Chronologically explainable: January OD -> March BD.
    Must NOT be treated as a contradiction!
    """
    with get_db_context() as db:
        p = make_patient(db)
        d1 = make_doc(db, p.id, "rx_jan.pdf", datetime.datetime(2026, 1, 15))
        d2 = make_doc(db, p.id, "rx_mar.pdf", datetime.datetime(2026, 3, 20))

        f1 = make_fact(db, p.id, d1.id, "Metformin 500mg OD", "Metformin 500 mg OD")
        f2 = make_fact(db, p.id, d2.id, "Metformin 500mg BD", "Metformin 500 mg BD")

        m1 = Medication(
            id=medication_id(),
            patient_id=p.id,
            fact_id=f1.id,
            canonical_name="metformin",
            raw_name="Metformin",
            strength_value=500.0,
            strength_unit="mg",
            dose_text="500mg",
            frequency_code="OD",
            frequency_text="once daily",
            route="oral",
            status="current",
            group_key=f"{p.id}_metformin",
            source_document_id=d1.id,
        )
        m2 = Medication(
            id=medication_id(),
            patient_id=p.id,
            fact_id=f2.id,
            canonical_name="metformin",
            raw_name="Metformin",
            strength_value=500.0,
            strength_unit="mg",
            dose_text="500mg",
            frequency_code="BD",
            frequency_text="twice daily",
            route="oral",
            status="current",
            group_key=f"{p.id}_metformin",
            source_document_id=d2.id,
        )
        db.add_all([m1, m2])
        db.commit()

        timelines = medication_service.reconcile_patient_medications(db, p.id)
        tl = timelines[0]
        assert tl["has_conflict"] is False
        assert tl["latest_change_type"] == ReconciliationChangeType.FREQUENCY_CHANGE.value
        assert "once daily" in tl["latest_change_reason"] or "OD" in tl["latest_change_reason"]
        assert "twice daily" in tl["latest_change_reason"] or "BD" in tl["latest_change_reason"]

        issues = contradiction_service.recompute(db, p.id)
        assert not any(i["issue_type"] == "medication_conflict" for i in issues)


def test_scenario_4_same_medication_discontinued(make_patient, make_doc, make_fact):
    """
    Scenario 4: Medication stopped/discontinued -> DISCONTINUED.
    """
    with get_db_context() as db:
        p = make_patient(db)
        d1 = make_doc(db, p.id, "rx_jan.pdf", datetime.datetime(2026, 1, 15))
        d2 = make_doc(db, p.id, "discharge_mar.pdf", datetime.datetime(2026, 3, 20))

        f1 = make_fact(db, p.id, d1.id, "Lisinopril 10mg", "Lisinopril 10mg OD")
        f2 = make_fact(db, p.id, d2.id, "Lisinopril stopped", "Lisinopril discontinued due to cough")

        m1 = Medication(
            id=medication_id(),
            patient_id=p.id,
            fact_id=f1.id,
            canonical_name="lisinopril",
            raw_name="Lisinopril",
            strength_value=10.0,
            strength_unit="mg",
            dose_text="10mg",
            frequency_code="OD",
            frequency_text="once daily",
            status="current",
            group_key=f"{p.id}_lisinopril",
            source_document_id=d1.id,
        )
        m2 = Medication(
            id=medication_id(),
            patient_id=p.id,
            fact_id=f2.id,
            canonical_name="lisinopril",
            raw_name="Lisinopril",
            strength_value=10.0,
            strength_unit="mg",
            dose_text="10mg",
            status="previous",
            status_reason="discontinued due to dry cough",
            group_key=f"{p.id}_lisinopril",
            source_document_id=d2.id,
        )
        db.add_all([m1, m2])
        db.commit()

        timelines = medication_service.reconcile_patient_medications(db, p.id)
        tl = timelines[0]
        assert tl["canonical_name"] == "lisinopril"
        assert tl["current_status"] == "discontinued"
        assert tl["latest_change_type"] == ReconciliationChangeType.DISCONTINUED.value


def test_scenario_5_same_medication_restarted(make_patient, make_doc, make_fact):
    """
    Scenario 5: Medication stopped then restarted -> RESTARTED.
    """
    with get_db_context() as db:
        p = make_patient(db)
        d1 = make_doc(db, p.id, "rx_jan.pdf", datetime.datetime(2026, 1, 1))
        d2 = make_doc(db, p.id, "rx_mar.pdf", datetime.datetime(2026, 3, 1))
        d3 = make_doc(db, p.id, "rx_jun.pdf", datetime.datetime(2026, 6, 1))

        f1 = make_fact(db, p.id, d1.id, "Atorvastatin 20mg", "Atorvastatin 20mg daily")
        f2 = make_fact(db, p.id, d2.id, "Atorvastatin stopped", "Atorvastatin paused")
        f3 = make_fact(db, p.id, d3.id, "Atorvastatin 10mg", "Atorvastatin resumed at 10mg daily")

        m1 = Medication(
            id=medication_id(),
            patient_id=p.id,
            fact_id=f1.id,
            canonical_name="atorvastatin",
            raw_name="Atorvastatin",
            strength_value=20.0,
            strength_unit="mg",
            dose_text="20mg",
            status="current",
            group_key=f"{p.id}_atorvastatin",
            source_document_id=d1.id,
        )
        m2 = Medication(
            id=medication_id(),
            patient_id=p.id,
            fact_id=f2.id,
            canonical_name="atorvastatin",
            raw_name="Atorvastatin",
            status="previous",
            group_key=f"{p.id}_atorvastatin",
            source_document_id=d2.id,
        )
        m3 = Medication(
            id=medication_id(),
            patient_id=p.id,
            fact_id=f3.id,
            canonical_name="atorvastatin",
            raw_name="Atorvastatin",
            strength_value=10.0,
            strength_unit="mg",
            dose_text="10mg",
            frequency_code="OD",
            frequency_text="daily",
            status="current",
            group_key=f"{p.id}_atorvastatin",
            source_document_id=d3.id,
        )
        db.add_all([m1, m2, m3])
        db.commit()

        timelines = medication_service.reconcile_patient_medications(db, p.id)
        tl = timelines[0]
        assert tl["canonical_name"] == "atorvastatin"
        assert tl["current_status"] == "current"
        assert len(tl["history"]) == 3
        assert tl["history"][0]["change_type"] == ReconciliationChangeType.NEW_MEDICATION.value
        assert tl["history"][1]["change_type"] == ReconciliationChangeType.DISCONTINUED.value
        assert tl["history"][2]["change_type"] == ReconciliationChangeType.RESTARTED.value
        assert tl["latest_change_type"] == ReconciliationChangeType.RESTARTED.value


def test_scenario_6_conflicting_same_date_instructions(make_patient, make_doc, make_fact):
    """
    Scenario 6: Conflicting instructions on same date -> CONFLICTING.
    Preserves both sources, flags conflict, never automatically resolves.
    """
    with get_db_context() as db:
        p = make_patient(db)
        same_date = datetime.datetime(2026, 9, 20)
        d1 = make_doc(db, p.id, "clinic_morning.pdf", same_date)
        d2 = make_doc(db, p.id, "hospital_evening.pdf", same_date)

        f1 = make_fact(db, p.id, d1.id, "Metformin 500mg OD", "Metformin 500mg OD")
        f2 = make_fact(db, p.id, d2.id, "Metformin 1000mg BD", "Metformin 1000mg BD")

        m1 = Medication(
            id=medication_id(),
            patient_id=p.id,
            fact_id=f1.id,
            canonical_name="metformin",
            raw_name="Metformin",
            strength_value=500.0,
            strength_unit="mg",
            dose_text="500mg",
            frequency_code="OD",
            frequency_text="once daily",
            status="current",
            group_key=f"{p.id}_metformin",
            source_document_id=d1.id,
        )
        m2 = Medication(
            id=medication_id(),
            patient_id=p.id,
            fact_id=f2.id,
            canonical_name="metformin",
            raw_name="Metformin",
            strength_value=1000.0,
            strength_unit="mg",
            dose_text="1000mg",
            frequency_code="BD",
            frequency_text="twice daily",
            status="current",
            group_key=f"{p.id}_metformin",
            source_document_id=d2.id,
        )
        db.add_all([m1, m2])
        db.commit()

        # Reconcile issues
        issues = medication_service.reconcile(db, p.id)
        assert len(issues) >= 1
        iss = issues[0]
        assert "Two records contain different Metformin instructions" in iss.description
        assert "clinic_morning.pdf" in iss.description
        assert "hospital_evening.pdf" in iss.description

        # Reconciled timeline reflects the conflict
        timelines = medication_service.reconcile_patient_medications(db, p.id)
        tl = timelines[0]
        assert tl["has_conflict"] is True
        assert tl["current_status"] == "conflicting"
        assert tl["history"][1]["change_type"] == ReconciliationChangeType.CONFLICTING.value
        assert "Conflicting instructions" in tl["history"][1]["change_description"]
        assert len(tl["evidence_references"]) >= 2


def test_scenario_7_missing_dosage(make_patient, make_doc, make_fact):
    """
    Scenario 7: Missing dosage is marked MISSING and never fabricated.
    """
    with get_db_context() as db:
        p = make_patient(db)
        d = make_doc(db, p.id, "referral.pdf", datetime.datetime(2026, 4, 1))
        f = make_fact(db, p.id, d.id, "Metformin", "Patient takes Metformin daily")

        m = Medication(
            id=medication_id(),
            patient_id=p.id,
            fact_id=f.id,
            canonical_name="metformin",
            raw_name="Metformin",
            strength_value=None,
            strength_unit=None,
            dose_text=None,
            frequency_code="OD",
            frequency_text="daily",
            status="current",
            group_key=f"{p.id}_metformin",
            source_document_id=d.id,
        )
        db.add(m)
        db.commit()

        timelines = medication_service.reconcile_patient_medications(db, p.id)
        tl = timelines[0]
        assert tl["current_dose"] is None
        assert tl["history"][0]["dose_semantic_state"] == "MISSING"
        assert tl["history"][0]["strength_value"] is None


def test_scenario_8_missing_frequency(make_patient, make_doc, make_fact):
    """
    Scenario 8: Missing frequency is left None and never guessed.
    """
    with get_db_context() as db:
        p = make_patient(db)
        d = make_doc(db, p.id, "discharge.pdf", datetime.datetime(2026, 4, 1))
        f = make_fact(db, p.id, d.id, "Amlodipine 5mg", "Amlodipine 5mg")

        m = Medication(
            id=medication_id(),
            patient_id=p.id,
            fact_id=f.id,
            canonical_name="amlodipine",
            raw_name="Amlodipine 5mg",
            strength_value=5.0,
            strength_unit="mg",
            dose_text="5mg",
            frequency_code="other",
            frequency_text=None,
            status="current",
            group_key=f"{p.id}_amlodipine",
            source_document_id=d.id,
        )
        db.add(m)
        db.commit()

        timelines = medication_service.reconcile_patient_medications(db, p.id)
        tl = timelines[0]
        assert tl["canonical_name"] == "amlodipine"
        assert tl["current_dose"] == "5mg"
        assert tl["current_frequency"] in (None, "other")


def test_scenario_9_brand_generic_variations(make_patient, make_doc, make_fact):
    """
    Scenario 9: Brand and generic variations (e.g. Glucophage -> Metformin)
    are recognized as the same medication and reconciled into a single timeline.
    """
    with get_db_context() as db:
        p = make_patient(db)
        d1 = make_doc(db, p.id, "rx_private_clinic.pdf", datetime.datetime(2026, 1, 10))
        d2 = make_doc(db, p.id, "hospital_notes.pdf", datetime.datetime(2026, 4, 15))

        f1 = make_fact(db, p.id, d1.id, "Glucophage 500mg OD", "Glucophage 500mg OD")
        f2 = make_fact(db, p.id, d2.id, "Metformin 1000mg OD", "Metformin 1000mg OD")

        m1 = Medication(
            id=medication_id(),
            patient_id=p.id,
            fact_id=f1.id,
            canonical_name="metformin",
            raw_name="Glucophage",
            strength_value=500.0,
            strength_unit="mg",
            dose_text="500mg",
            frequency_code="OD",
            frequency_text="once daily",
            status="current",
            group_key=f"{p.id}_metformin",
            source_document_id=d1.id,
        )
        m2 = Medication(
            id=medication_id(),
            patient_id=p.id,
            fact_id=f2.id,
            canonical_name="metformin",
            raw_name="Metformin",
            strength_value=1000.0,
            strength_unit="mg",
            dose_text="1000mg",
            frequency_code="OD",
            frequency_text="once daily",
            status="current",
            group_key=f"{p.id}_metformin",
            source_document_id=d2.id,
        )
        db.add_all([m1, m2])
        db.commit()

        timelines = medication_service.reconcile_patient_medications(db, p.id)
        # Should be a SINGLE timeline for metformin, recognizing Glucophage as brand
        assert len(timelines) == 1
        tl = timelines[0]
        assert tl["canonical_name"] == "metformin"
        assert "Glucophage" in tl["brand_names"]
        assert len(tl["history"]) == 2
        assert tl["latest_change_type"] == ReconciliationChangeType.DOSE_CHANGE.value


def test_scenario_10_completely_unrelated_medications(make_patient, make_doc, make_fact):
    """
    Scenario 10: Completely unrelated medications (Metformin vs Lisinopril)
    are maintained in completely separate timelines and never compared.
    """
    with get_db_context() as db:
        p = make_patient(db)
        d = make_doc(db, p.id, "prescription.pdf", datetime.datetime(2026, 2, 1))

        f1 = make_fact(db, p.id, d.id, "Metformin 500mg OD", "Metformin 500mg OD")
        f2 = make_fact(db, p.id, d.id, "Lisinopril 10mg OD", "Lisinopril 10mg OD")

        m1 = Medication(
            id=medication_id(),
            patient_id=p.id,
            fact_id=f1.id,
            canonical_name="metformin",
            raw_name="Metformin",
            strength_value=500.0,
            strength_unit="mg",
            dose_text="500mg",
            frequency_code="OD",
            status="current",
            group_key=f"{p.id}_metformin",
            source_document_id=d.id,
        )
        m2 = Medication(
            id=medication_id(),
            patient_id=p.id,
            fact_id=f2.id,
            canonical_name="lisinopril",
            raw_name="Lisinopril",
            strength_value=10.0,
            strength_unit="mg",
            dose_text="10mg",
            frequency_code="OD",
            status="current",
            group_key=f"{p.id}_lisinopril",
            source_document_id=d.id,
        )
        db.add_all([m1, m2])
        db.commit()

        timelines = medication_service.reconcile_patient_medications(db, p.id)
        assert len(timelines) == 2
        drug_names = {t["canonical_name"] for t in timelines}
        assert drug_names == {"metformin", "lisinopril"}
        for tl in timelines:
            assert tl["has_conflict"] is False
            assert len(tl["history"]) == 1
            assert tl["history"][0]["change_type"] == ReconciliationChangeType.NEW_MEDICATION.value
