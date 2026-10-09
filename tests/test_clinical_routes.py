import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import get_db_context
from app.models.patient import Patient
from app.utils.ids import patient_id

client = TestClient(app)

def test_clinical_routes_endpoints():
    with get_db_context() as db:
        pid = patient_id()
        p = Patient(id=pid, full_name="Route Testing Patient")
        db.add(p)
        db.commit()

    # 1. Facts endpoint
    res_facts = client.get(f"/api/v1/patients/{pid}/facts")
    assert res_facts.status_code == 200
    assert res_facts.json()["success"] is True

    # 2. Timeline endpoint
    res_tl = client.get(f"/api/v1/patients/{pid}/timeline")
    assert res_tl.status_code == 200
    assert res_tl.json()["success"] is True

    # 3. Medications endpoint
    res_meds = client.get(f"/api/v1/patients/{pid}/medications")
    assert res_meds.status_code == 200
    assert res_meds.json()["success"] is True

    # 4. Investigations endpoint
    res_inv = client.get(f"/api/v1/patients/{pid}/investigations")
    assert res_inv.status_code == 200
    assert res_inv.json()["success"] is True

    # 5. Issues endpoint
    res_iss = client.get(f"/api/v1/patients/{pid}/issues")
    assert res_iss.status_code == 200
    assert res_iss.json()["success"] is True

    print("\n✓ Phase 5 Clinical Routes endpoints tested and verified!")
