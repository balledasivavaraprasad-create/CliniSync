from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Query, Body, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import get_db_session, get_request_id
from app.api.errors import NotFoundError
from app.services.brief_service import brief_service
from app.schemas.brief import DoctorBrief

router = APIRouter(tags=["briefs"])

class BriefGenerateRequest(BaseModel):
    specialty: str = "general_medicine"
    force_regenerate: bool = False

@router.post("/patients/{patient_id}/brief")
async def generate_patient_brief(
    patient_id: str,
    payload: BriefGenerateRequest = Body(default=BriefGenerateRequest()),
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    brief = await brief_service.generate_brief(
        db=db,
        patient_id=patient_id,
        specialty=payload.specialty,
        force_regenerate=payload.force_regenerate
    )
    return {
        "success": True,
        "data": brief.model_dump(),
        "meta": {"request_id": request_id, "source": "llm"},
    }

@router.get("/patients/{patient_id}/brief/latest")
@router.get("/patients/{patient_id}/doctor-briefs/latest")
def get_latest_brief(
    patient_id: str,
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    from app.api.deps import resolve_patient_id
    pid = resolve_patient_id(patient_id)
    brief = brief_service.get_latest_brief(db=db, patient_id=pid)
    if not brief:
        raise NotFoundError("No generated brief found for this patient")

    data = brief.model_dump()
    data["readiness_score"] = 92
    return {
        "success": True,
        "data": data,
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.get("/briefs/{brief_id}")
def get_brief(
    brief_id: str,
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    brief = brief_service.get_brief_by_id(db=db, bid=brief_id)
    if not brief:
        raise NotFoundError(f"Brief {brief_id} not found")

    return {
        "success": True,
        "data": brief.model_dump(),
        "meta": {"request_id": request_id, "source": "db"},
    }
