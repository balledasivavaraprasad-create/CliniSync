import pytest
import time
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import get_db_context
from app.models.patient import Patient
from app.models.clinical_fact import ClinicalFact
from app.models.medication import Medication
from app.models.investigation import Investigation
from app.utils.ids import patient_id, fact_id, medication_id, investigation_id
from app.services.brief_service import brief_service
from app.schemas.brief import DoctorBrief

client = TestClient(app)

@pytest.mark.anyio
async def test_brief_generation_and_caching():
    with get_db_context() as db:
        pid = patient_id()
        p = Patient(id=pid, full_name="Brief Test Patient", age_years=52)
        db.add(p)
        db.flush()

        f1 = ClinicalFact(
            id=fact_id(),
            patient_id=pid,
            fact_type="diagnosis",
            value="Type 2 Diabetes Mellitus",
            source_text="Type 2 Diabetes Mellitus",
            provenance_verified=True,
            confidence=0.95
        )
        f2 = ClinicalFact(
            id=fact_id(),
            patient_id=pid,
            fact_type="medication",
            value="metformin 500 mg",
            source_text="metformin 500 mg",
            provenance_verified=True,
            confidence=0.95
        )
        db.add_all([f1, f2])
        db.flush()

        m1 = Medication(
            id=medication_id(),
            patient_id=pid,
            fact_id=f2.id,
            canonical_name="metformin",
            raw_name="Metformin",
            strength_value=500.0,
            strength_unit="mg",
            dose_text="500 mg",
            frequency_code="OD",
            group_key=f"{pid}_metformin",
            confidence=0.95
        )
        db.add(m1)
        db.commit()

    # 1. Test Deterministic Template Brief builder directly
    with get_db_context() as db:
        pt = db.query(Patient).filter(Patient.id == pid).first()
        facts = db.query(ClinicalFact).filter(ClinicalFact.patient_id == pid).all()
        meds = db.query(Medication).filter(Medication.patient_id == pid).all()
        template_brief = brief_service._build_deterministic_template_brief(
            patient=pt,
            specialty="general_medicine",
            facts=facts,
            meds=meds,
            invs=[],
            issues=[]
        )
        assert template_brief.patient.name == "Brief Test Patient"
        assert len(template_brief.current_medications) == 1
        assert template_brief.current_medications[0].name == "Metformin"
        assert len(template_brief.allergies) >= 1  # Mandatory allergies section
        assert template_brief.disclaimer != ""

    # 2. Test Brief Generation via Service
    with get_db_context() as db:
        start_t = time.time()
        brief = await brief_service.generate_brief(db=db, patient_id=pid, specialty="general_medicine")
        gen_duration = time.time() - start_t
        assert brief is not None
        assert isinstance(brief, DoctorBrief)
        assert len(brief.current_medications) >= 1

        # 3. Test Cached Retrieval (< 200 ms target)
        cache_start = time.time()
        cached = await brief_service.generate_brief(db=db, patient_id=pid, specialty="general_medicine")
        cache_duration = time.time() - cache_start
        assert cache_duration < 0.20, f"Cache retrieval took {cache_duration}s, expected < 0.20s"
        assert cached.patient.id == pid

    # 4. Test API Endpoints
    res = client.get(f"/api/v1/patients/{pid}/brief/latest")
    assert res.status_code == 200
    brief_data = res.json()["data"]
    assert brief_data["patient"]["name"] == "Brief Test Patient"
    assert "allergies" in brief_data

    print("\n✓ Phase 7 Doctor Brief Generation & Gate 2 Cache verified successfully!")
