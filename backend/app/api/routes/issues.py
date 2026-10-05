from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import get_db_session, get_current_user, get_request_id, CurrentUser
from app.services.contradiction_service import contradiction_service, IssueNotFoundError
from app.services.missing_info_service import missing_info_service
from app.services.derived_recompute import run_patient_recompute

__all__ = ["router", "IssueNotFoundError"]

router = APIRouter(tags=["issues"])

class IssuePatchRequest(BaseModel):
    status: Optional[str] = None
    doctor_note: Optional[str] = None

@router.get("/patients/{patient_id}/issues")
@router.get("/patients/{patient_id}/contradictions")
def list_issues(
    patient_id: str,
    type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    from app.api.deps import require_patient_id
    pid = require_patient_id(db, patient_id)
    issues = contradiction_service.get_patient_issues(
        db=db,
        patient_id=pid,
        issue_type=type,
        status=status,
        severity=severity
    )

    return {
        "success": True,
        "data": issues,
        "meta": {"request_id": request_id, "source": "db"},
    }

@router.patch("/issues/{issue_id}")
def patch_issue(
    issue_id: str,
    payload: IssuePatchRequest,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    # `patch_issue` raises `IssueNotFoundError` for an unknown id, which the
    # global handler maps to 404. Previously this surfaced as an opaque 500
    # `INTERNAL_ERROR`, which the Flutter client could not distinguish from a
    # real server fault (docs/frontend/API_MISMATCHES.md M-06).
    updated = contradiction_service.patch_issue(
        db=db,
        issue_id=issue_id,
        status=payload.status,
        doctor_note=payload.doctor_note
    )
    return {
        "success": True,
        "data": updated,
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.post("/patients/{patient_id}/issues/recompute")
async def recompute_issues(
    patient_id: str,
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    from app.api.deps import require_patient_id
    pid = require_patient_id(db, patient_id)
    await run_patient_recompute(pid)
    all_issues = contradiction_service.get_patient_issues(db=db, patient_id=pid)
    return {
        "success": True,
        "data": all_issues,
        "meta": {"request_id": request_id, "source": "db"},
    }
