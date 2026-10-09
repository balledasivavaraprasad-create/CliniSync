import pytest
import datetime
from sqlalchemy.orm import Session
from app.db.database import get_db_context
from app.models.patient import Patient
from app.models.document import Document
from app.models.clinical_fact import ClinicalFact
from app.models.medication import Medication
from app.models.investigation import Investigation
from app.utils.ids import patient_id, document_id, fact_id, medication_id, investigation_id
from app.services.medication_service import medication_service
from app.services.lab_service import lab_service
from app.services.contradiction_service import contradiction_service
from app.services.missing_info_service import missing_info_service
from app.services.timeline_service import timeline_service
from app.schemas.common import FactType, VerificationStatus

@pytest.mark.anyio
async def test_clinical_intelligence_invariants_and_services():
    with get_db_context() as db:
        # 1. Create Patient
        pid = patient_id()
        p = Patient(id=pid, full_name="Clinical Intelligence Test Patient")
        db.add(p)
        db.flush()

        # 2. Create Two Documents (Conflicting Prescriptions)
        d1 = Document(
            id=document_id(),
            patient_id=pid,
            original_filename="prescription_sep_morning.pdf",
            stored_path="storage/dummy1.pdf",
            mime_type="application/pdf",
            file_size=1024,
            sha256="sha_dummy_1",
            document_date=datetime.datetime(2026, 9, 20),
            processing_status="complete"
        )
        d2 = Document(
            id=document_id(),
            patient_id=pid,
            original_filename="prescription_sep_evening.pdf",
            stored_path="storage/dummy2.pdf",
            mime_type="application/pdf",
            file_size=1024,
            sha256="sha_dummy_2",
            document_date=datetime.datetime(2026, 9, 20),  # SAME DATE
            processing_status="complete"
        )
        db.add_all([d1, d2])
        db.flush()

        # 3. Create Conflicting Medication Facts & Rows (Metformin 500mg OD vs Metformin 500mg BD)
        f1 = ClinicalFact(
            id=fact_id(),
            patient_id=pid,
            document_id=d1.id,
            fact_type=FactType.medication.value,
            value="metformin 500.0 mg",
            source_text="Tab Metformin 500mg OD",
            source_page=1,
            provenance_verified=True,
            confidence=0.95
        )
        f2 = ClinicalFact(
            id=fact_id(),
            patient_id=pid,
            document_id=d2.id,
            fact_type=FactType.medication.value,
            value="metformin 500.0 mg",
            source_text="Tab Metformin 500mg BD",
            source_page=1,
            provenance_verified=True,
            confidence=0.95
        )
        db.add_all([f1, f2])
        db.flush()

        m1 = Medication(
            id=medication_id(),
            patient_id=pid,
            fact_id=f1.id,
            canonical_name="metformin",
            raw_name="Metformin",
            strength_value=500.0,
            strength_unit="mg",
            frequency_code="OD",
            frequency_text="once daily",
            group_key=f"{pid}_metformin",
            source_document_id=d1.id,
            confidence=0.95
        )
        m2 = Medication(
            id=medication_id(),
            patient_id=pid,
            fact_id=f2.id,
            canonical_name="metformin",
            raw_name="Metformin",
            strength_value=500.0,
            strength_unit="mg",
            frequency_code="BD",
            frequency_text="twice daily",
            group_key=f"{pid}_metformin",
            source_document_id=d2.id,
            confidence=0.95
        )
        db.add_all([m1, m2])

        # 4. Create Longitudinal Lab Facts (HbA1c: 8.4 -> 8.0 -> 7.8)
        lab_dates = [
            datetime.date(2026, 1, 15),
            datetime.date(2026, 4, 10),
            datetime.date(2026, 9, 20)
        ]
        lab_vals = [8.4, 8.0, 7.8]
        for dt, val in zip(lab_dates, lab_vals):
            inv_fact = ClinicalFact(
                id=fact_id(),
                patient_id=pid,
                document_id=d1.id,
                fact_type=FactType.investigation.value,
                value=f"hba1c: {val} %",
                source_text=f"HbA1c {val}%",
                source_page=1,
                provenance_verified=True,
                confidence=0.95
            )
            db.add(inv_fact)
            db.flush()

            inv = Investigation(
                id=investigation_id(),
                patient_id=pid,
                fact_id=inv_fact.id,
                test_name_raw="HbA1c",
                test_name_canonical="hba1c",
                value_numeric=val,
                value_text=str(val),
                unit="%",
                reference_low=4.0,
                reference_high=5.6,
                reference_text="< 5.7%",
                abnormal_flag="high",
                observed_date=dt,
                source_document_id=d1.id,
                confidence=0.95,
                group_key=f"{pid}_hba1c"
            )
            db.add(inv)

        # 5. Add a diagnosis for diabetes (to test missing info checklist)
        diag_fact = ClinicalFact(
            id=fact_id(),
            patient_id=pid,
            document_id=d1.id,
            fact_type=FactType.diagnosis.value,
            value="Type 2 Diabetes Mellitus",
            source_text="Type 2 Diabetes Mellitus",
            source_page=1,
            provenance_verified=True,
            confidence=0.95
        )
        db.add(diag_fact)
        db.commit()

    # --- TEST MEDICATION RECONCILIATION & INV-4 ---
    with get_db_context() as db:
        conflicts = medication_service.reconcile(db, pid)
        assert len(conflicts) >= 1
        conflict_desc = conflicts[0].description
        # Invariant 4: System must NEVER state a correct dose. Output comparison template only.
        assert "Two records contain different Metformin instructions" in conflict_desc
        assert "OD" in conflict_desc or "once daily" in conflict_desc
        assert "BD" in conflict_desc or "twice daily" in conflict_desc
        assert "you should" not in conflict_desc.lower()
        assert "correct dose is" not in conflict_desc.lower()

    # --- TEST LAB INTELLIGENCE & INV-6 ---
    with get_db_context() as db:
        trend = lab_service.get_investigation_trend(db, pid, "hba1c")
        assert trend["direction"] == "down"
        assert trend["delta"] == -0.6
        # Invariant 6: Trends are described non-causally
        desc = trend["description"]
        assert "decreasing" in desc.lower()
        # Verify no causal words
        for banned in ["due to", "caused by", "because of", "improved by"]:
            assert banned not in desc.lower()

    # --- TEST MISSING INFO CHECKLIST & INV-5 ---
    with get_db_context() as db:
        missing_items = missing_info_service.recompute(db, pid)
        assert len(missing_items) >= 1
        # Invariant 5: Phrased as "Potentially missing: ..." with reason
        for item in missing_items:
            assert item["prompt"].startswith("Potentially missing:")
            assert len(item["reason"]) > 5

    print("\n✓ Phase 5 Clinical Intelligence (Invariants INV-4, INV-5, INV-6) verified successfully!")
