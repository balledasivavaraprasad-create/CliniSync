from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    get_db_session,
    get_request_id,
    get_current_user,
    CurrentUser,
    require_patient_access,
)
from app.services.medication_service import medication_service

router = APIRouter(tags=["medications"])

@router.get("/patients/{patient_id}/medications")
def list_medications(
    patient_id: str,
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    pid = require_patient_access(patient_id, db, user)
    meds = medication_service.get_patient_medications(db=db, patient_id=pid, status=status)
    return {
        "success": True,
        "data": meds,
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.get("/patients/{patient_id}/medications/reconciliation")
def get_medication_reconciliation(
    patient_id: str,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    from app.models.contradiction import Contradiction
    pid = require_patient_access(patient_id, db, user)
    meds = medication_service.get_patient_medications(db=db, patient_id=pid)
    conflicts = db.query(Contradiction).filter(
        Contradiction.patient_id == pid,
        Contradiction.issue_type == "medication_conflict"
    ).all()
    reconciled_timelines = medication_service.reconcile_patient_medications(db=db, patient_id=pid)

    return {
        "success": True,
        "data": {
            "patient_id": pid,
            "medications": meds,
            "active_medications": [m for m in meds if m.get("status") == "current"],
            "conflicts": [
                {
                    "id": c.id,
                    "medication": c.title,
                    "warning": c.description,
                    "severity": c.severity,
                    "status": c.status,
                }
                for c in conflicts
            ],
            "total_active": len([m for m in meds if m.get("status") == "current"]),
            "reconciled_medications": reconciled_timelines,
        },
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.get("/patients/{patient_id}/medications/{group_key}/history")
def get_medication_history(
    patient_id: str,
    group_key: str,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    pid = require_patient_access(patient_id, db, user)
    history = medication_service.get_medication_history(db=db, patient_id=pid, group_key=group_key)
    return {
        "success": True,
        "data": history,
        "meta": {"request_id": request_id, "source": "db"},
    }
