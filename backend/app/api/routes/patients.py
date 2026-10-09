from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_db_session,
    get_current_user,
    get_request_id,
    CurrentUser,
    get_accessible_patient_ids,
)
from app.api.errors import ForbiddenError
from app.schemas.patient import PatientCreate, PatientResponse, PatientOverviewResponse
from app.services.patient_service import PatientService

router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: PatientCreate,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    if not (user.is_clinical or user.is_admin):
        raise ForbiddenError("Only clinical staff or administrators can create patient records.")
    patient = PatientService.create(db, payload, actor=user.id, request_id=request_id)
    return {
        "success": True,
        "data": PatientResponse.model_validate(patient).model_dump(),
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.get("")
def list_patients(
    query: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    accessible_ids = get_accessible_patient_ids(db, user)
    patients = PatientService.list(
        db,
        query=query,
        limit=limit,
        offset=offset,
        accessible_ids=accessible_ids,
    )
    return {
        "success": True,
        "data": [PatientResponse.model_validate(p).model_dump() for p in patients],
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.get("/{id}")
def get_patient(
    id: str,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    from app.api.deps import require_patient_access
    pid = require_patient_access(id, db, user)
    patient = PatientService.get(db, pid)
    return {
        "success": True,
        "data": PatientResponse.model_validate(patient).model_dump(),
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.get("/{id}/overview")
def get_patient_overview(
    id: str,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    from app.api.deps import require_patient_access
    pid = require_patient_access(id, db, user)
    overview = PatientService.get_overview(db, pid)
    # Serialize patient model
    overview["patient"] = PatientResponse.model_validate(overview["patient"]).model_dump()
    return {
        "success": True,
        "data": overview,
        "meta": {"request_id": request_id, "source": "db"},
    }
