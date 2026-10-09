from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Query, Body, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import (
    get_db_session,
    get_request_id,
    get_current_user,
    CurrentUser,
    require_patient_access,
    check_patient_authorization,
)
from app.api.errors import NotFoundError, ForbiddenError
from app.services.brief_service import brief_service
from app.models.brief import Brief
from app.schemas.brief import DoctorBrief

router = APIRouter(tags=["briefs"])

class BriefGenerateRequest(BaseModel):
    specialty: str = "general_medicine"
    force_regenerate: bool = False
    deterministic_only: bool = False
    mode: str = "auto"  # "auto" | "deterministic"

def _readiness_score(brief) -> int:
    groups = [
        getattr(brief, "chief_complaint", None),
        *(getattr(brief, "relevant_history", None) or []),
        *(getattr(brief, "current_medications", None) or []),
        *(getattr(brief, "recent_investigations", None) or []),
    ]
    groups = [g for g in groups if g is not None]

    total = len(groups)
    if total == 0:
        return 0

    with_evidence = sum(1 for g in groups if getattr(g, "evidence_ids", None))

    attention = len(getattr(brief, "contradictions", None) or []) + len(
        getattr(brief, "missing_information", None) or []
    )
    review = max(0, 100 - int(100 * attention / max(total, 1)))

    coverage = int(round(100 * with_evidence / total))
    return max(25, min(100, round(0.7 * coverage + 0.3 * review)))


@router.post("/patients/{patient_id}/brief")
async def generate_patient_brief(
    patient_id: str,
    payload: BriefGenerateRequest = Body(default=BriefGenerateRequest()),
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    if not (user.is_clinical or user.is_admin):
        raise ForbiddenError("Only clinical staff or administrators can generate doctor briefs.")
    pid = require_patient_access(patient_id, db, user)
    use_deterministic = payload.deterministic_only or payload.mode.lower() == "deterministic"
    brief, gen_source = await brief_service.generate_brief(
        db=db,
        patient_id=pid,
        specialty=payload.specialty,
        force_regenerate=payload.force_regenerate,
        actor=user.id,
        request_id=request_id,
        deterministic_only=use_deterministic,
    )
    return {
        "success": True,
        "data": brief.model_dump(),
        "meta": {
            "request_id": request_id,
            "source": "deterministic" if gen_source == "deterministic_template" else ("fallback" if gen_source != "llm" else "llm"),
        },
    }

@router.post("/patients/{patient_id}/brief/deterministic")
def generate_patient_brief_deterministic(
    patient_id: str,
    payload: BriefGenerateRequest = Body(default=BriefGenerateRequest()),
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    """
    Dedicated endpoint to generate a 100% deterministic DoctorBrief without calling any LLM.
    Guarantees zero model hallucinations and runs purely on verified structured records.
    """
    if not (user.is_clinical or user.is_admin):
        raise ForbiddenError("Only clinical staff or administrators can generate doctor briefs.")
    pid = require_patient_access(patient_id, db, user)
    brief = brief_service.generate_deterministic_brief(
        db=db,
        patient_id=pid,
        specialty=payload.specialty,
        actor=user.id,
        request_id=request_id,
        force_regenerate=payload.force_regenerate,
    )
    return {
        "success": True,
        "data": brief.model_dump(),
        "meta": {
            "request_id": request_id,
            "source": "deterministic",
        },
    }

@router.get("/patients/{patient_id}/brief/latest")
@router.get("/patients/{patient_id}/doctor-briefs/latest")
def get_latest_brief(
    patient_id: str,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    pid = require_patient_access(patient_id, db, user)
    brief = brief_service.get_latest_brief(db=db, patient_id=pid)
    if not brief:
        raise NotFoundError("No generated brief found for this patient")

    data = brief.model_dump()
    data["readiness_score"] = _readiness_score(brief)
    return {
        "success": True,
        "data": data,
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.get("/briefs/{brief_id}")
def get_brief(
    brief_id: str,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    b = db.query(Brief).filter(Brief.id == brief_id).first()
    if not b:
        raise NotFoundError(f"Brief {brief_id} not found")

    if not check_patient_authorization(db, user, b.patient_id):
        raise ForbiddenError(f"User '{user.id}' is not authorized to access brief '{brief_id}'.")

    brief = brief_service.get_brief_by_id(db=db, bid=brief_id)
    return {
        "success": True,
        "data": brief.model_dump(),
        "meta": {"request_id": request_id, "source": "db"},
    }
