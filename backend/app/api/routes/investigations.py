from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_request_id
from app.services.lab_service import lab_service

router = APIRouter(tags=["investigations"])

@router.get("/patients/{patient_id}/investigations")
def list_investigations(
    patient_id: str,
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    from app.api.deps import require_patient_id
    pid = require_patient_id(db, patient_id)
    invs = lab_service.get_latest_investigations(db=db, patient_id=pid)
    return {
        "success": True,
        "data": invs,
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.get("/patients/{patient_id}/investigations/trends")
def get_all_investigation_trends(
    patient_id: str,
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    from app.api.deps import require_patient_id
    from app.models.investigation import Investigation
    pid = require_patient_id(db, patient_id)
    canonical_tests = db.query(Investigation.test_name_canonical).filter(
        Investigation.patient_id == pid
    ).distinct().all()

    trends = []
    for (t_canon,) in canonical_tests:
        tr = lab_service.get_investigation_trend(db=db, patient_id=pid, group_key=t_canon)
        points = [
            {
                "date": s.get("date"),
                "value": s.get("value"),
                "unit": s.get("unit"),
                "flag": s.get("abnormal_flag"),
            }
            for s in tr.get("series", [])
        ]
        tr["points"] = points
        tr["test_name"] = tr.get("test", t_canon)
        trends.append(tr)

    return {
        "success": True,
        "data": trends,
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.get("/patients/{patient_id}/investigations/{group_key}/trend")
def get_investigation_trend(
    patient_id: str,
    group_key: str,
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    from app.api.deps import require_patient_id
    pid = require_patient_id(db, patient_id)
    trend = lab_service.get_investigation_trend(db=db, patient_id=pid, group_key=group_key)
    return {
        "success": True,
        "data": trend,
        "meta": {"request_id": request_id, "source": "db"},
    }

