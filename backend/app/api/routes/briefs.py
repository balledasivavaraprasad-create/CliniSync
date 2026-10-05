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

def _readiness_score(brief) -> int:
    """How much of the brief rests on verified, evidence-linked input.

    Replaces a hardcoded `92`, which the Flutter client renders as a progress
    ring and which therefore reads as a clinical metric while being a constant
    (docs/frontend/API_MISMATCHES.md M-18). Each component is a real count:

    * sources resolvable — brief items carrying at least one evidence id;
    * evidence coverage — statements that carry one;
    * review pressure — 100 when nothing needs the doctor's attention, less per
      open contradiction or missing-information item.

    It is a completeness indicator for the brief, never a judgement about the
    patient.
    """
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

    # Coverage dominates; review pressure can pull it down to at most a quarter.
    coverage = int(round(100 * with_evidence / total))
    return max(25, min(100, round(0.7 * coverage + 0.3 * review)))


@router.post("/patients/{patient_id}/brief")
async def generate_patient_brief(
    patient_id: str,
    payload: BriefGenerateRequest = Body(default=BriefGenerateRequest()),
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    from app.api.deps import require_patient_id
    pid = require_patient_id(db, patient_id)
    # `generate_brief` returns the brief it persisted, plus the source it
    # actually used, so the envelope can be honest when the deterministic
    # template served the request instead of the LLM.
    brief, gen_source = await brief_service.generate_brief(
        db=db,
        patient_id=pid,
        specialty=payload.specialty,
        force_regenerate=payload.force_regenerate
    )
    return {
        "success": True,
        "data": brief.model_dump(),
        "meta": {
            "request_id": request_id,
            "source": "fallback" if gen_source != "llm" else "llm",
        },
    }

@router.get("/patients/{patient_id}/brief/latest")
@router.get("/patients/{patient_id}/doctor-briefs/latest")
def get_latest_brief(
    patient_id: str,
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    from app.api.deps import require_patient_id
    pid = require_patient_id(db, patient_id)
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
