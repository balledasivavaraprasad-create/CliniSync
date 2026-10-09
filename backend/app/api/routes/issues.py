from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import (
    get_db_session,
    get_current_user,
    get_request_id,
    CurrentUser,
    require_patient_access,
    check_patient_authorization,
)
from app.services.contradiction_service import contradiction_service, IssueNotFoundError
from app.services.missing_info_service import missing_info_service
from app.services.derived_recompute import run_patient_recompute
from app.models.contradiction import Contradiction
from app.api.errors import ForbiddenError

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
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    pid = require_patient_access(patient_id, db, user)
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
    # Verify authorization for the patient this issue belongs to
    iss = db.query(Contradiction).filter(Contradiction.id == issue_id).first()
    if not iss:
        raise IssueNotFoundError(f"Review item {issue_id} not found.")

    if not (user.is_clinical or user.is_admin):
        raise ForbiddenError("Only clinical staff or administrators can modify clinical review items.")

    if not check_patient_authorization(db, user, iss.patient_id):
        raise ForbiddenError(f"User '{user.id}' is not authorized to modify issue '{issue_id}'.")

    updated = contradiction_service.patch_issue(
        db=db,
        issue_id=issue_id,
        status=payload.status,
        doctor_note=payload.doctor_note,
        actor=user.id,
        request_id=request_id,
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
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    if not (user.is_clinical or user.is_admin):
        raise ForbiddenError("Only clinical staff or administrators can trigger issue recomputation.")
    pid = require_patient_access(patient_id, db, user)
    await run_patient_recompute(pid)
    all_issues = contradiction_service.get_patient_issues(db=db, patient_id=pid)
    return {
        "success": True,
        "data": all_issues,
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.get("/issues/source-priority-policy")
def get_source_priority_policy(
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    """Returns the current configurable source hierarchy for conflicting clinical information."""
    from app.services.source_priority_policy import source_priority_policy
    return {
        "success": True,
        "data": {
            "hierarchy": source_priority_policy.hierarchy,
            "description": "Ranked source authority hierarchy from highest authority to lowest authority.",
            "rule": "Conflicts are never silently resolved or overwritten; lower-ranked records are preserved alongside higher-ranked records."
        },
        "meta": {"request_id": request_id, "source": "config"},
    }


class SourcePriorityPolicyUpdateRequest(BaseModel):
    hierarchy: List[str]


@router.put("/issues/source-priority-policy")
def update_source_priority_policy(
    payload: SourcePriorityPolicyUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    """Allows administrators and clinical staff to configure the clinical source authority hierarchy."""
    if not (user.is_admin or user.is_clinical):
        raise ForbiddenError("Only clinical staff or administrators can update the source priority policy.")
    from app.services.source_priority_policy import source_priority_policy
    source_priority_policy.set_hierarchy(payload.hierarchy)
    return {
        "success": True,
        "data": {
            "hierarchy": source_priority_policy.hierarchy,
            "updated": True,
        },
        "meta": {"request_id": request_id, "source": "config"},
    }
