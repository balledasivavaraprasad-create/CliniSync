from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Body, Header, status
from sqlalchemy.orm import Session
import json

from app.api.deps import (
    get_db_session,
    get_current_user,
    get_request_id,
    CurrentUser,
    require_patient_access,
    check_patient_authorization,
    require_role,
)
from app.api.errors import NotFoundError, ForbiddenError
from app.services.consultation_service import consultation_service
from app.models.consultation import Consultation
from app.schemas.consultation import (
    ConsultationCreateRequest,
    ConsultationUpdateRequest,
    ConsultationVersionCreateRequest,
    ConsultationApproveRequest
)

router = APIRouter(tags=["consultations"])


def _require_consultation_access(db: Session, user: CurrentUser, cid: str) -> Consultation:
    cns = db.query(Consultation).filter(Consultation.id == cid).first()
    if not cns:
        raise NotFoundError(f"Consultation {cid} not found")
    if not check_patient_authorization(db, user, cns.patient_id):
        raise ForbiddenError(f"User '{user.id}' is not authorized to access consultation '{cid}'.")
    return cns


@router.get("/patients/{patient_id}/consultations")
def list_patient_consultations(
    patient_id: str,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    pid = require_patient_access(patient_id, db, user)
    consultations = consultation_service.list_by_patient(db, pid)
    return {
        "success": True,
        "data": [
            {
                "id": c.id,
                "patient_id": c.patient_id,
                "specialty": c.specialty,
                "status": c.status,
                "current_version_id": c.current_version_id,
                "approved_at": c.approved_at.isoformat() if c.approved_at else None,
                "approved_by": c.approved_by,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in consultations
        ],
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.post("/patients/{patient_id}/consultations", status_code=status.HTTP_201_CREATED)
async def create_consultation(
    patient_id: str,
    payload: ConsultationCreateRequest = Body(default=ConsultationCreateRequest()),
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    if not (user.is_clinical or user.is_admin):
        raise ForbiddenError("Only clinical staff or administrators can create consultation drafts.")
    pid = require_patient_access(patient_id, db, user)
    effective_key = payload.idempotency_key or idempotency_key
    cns, ver = await consultation_service.create_draft(
        db=db,
        patient_id=pid,
        specialty=payload.specialty,
        brief_id=payload.brief_id,
        actor=user.id,
        request_id=request_id,
        idempotency_key=effective_key,
    )
    return {
        "success": True,
        "data": {
            "id": cns.id,
            "patient_id": cns.patient_id,
            "specialty": cns.specialty,
            "status": cns.status,
            "current_version_id": cns.current_version_id,
            "version": {
                "id": ver.id,
                "version_number": ver.version_number,
                "origin": ver.origin,
                "content": json.loads(ver.content_json) if ver.content_json else {},
                "change_summary": ver.change_summary
            }
        },
        "meta": {"request_id": request_id, "source": "llm"},
    }

@router.get("/consultations/{consultation_id}")
def get_consultation(
    consultation_id: str,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    _require_consultation_access(db, user, consultation_id)
    cns, ver = consultation_service.get_consultation(db, consultation_id)
    return {
        "success": True,
        "data": {
            "id": cns.id,
            "patient_id": cns.patient_id,
            "specialty": cns.specialty,
            "status": cns.status,
            "current_version_id": cns.current_version_id,
            "approved_at": cns.approved_at.isoformat() if cns.approved_at else None,
            "approved_by": cns.approved_by,
            "current_version": {
                "id": ver.id if ver else None,
                "version_number": ver.version_number if ver else 1,
                "origin": ver.origin if ver else "ai_generated",
                "content": json.loads(ver.content_json) if (ver and ver.content_json) else {},
                "change_summary": ver.change_summary if ver else None
            } if ver else None
        },
        "meta": {"request_id": request_id, "source": "db"},
    }

@router.put("/consultations/{consultation_id}")
def update_consultation_draft(
    consultation_id: str,
    payload: ConsultationUpdateRequest,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    _require_consultation_access(db, user, consultation_id)
    updated_ver = consultation_service.update_draft(
        db=db,
        cid=consultation_id,
        content=payload.content,
        actor=user.id,
        expected_version_id=payload.expected_version_id,
        request_id=request_id,
    )
    return {
        "success": True,
        "data": {
            "consultation_id": consultation_id,
            "version_id": updated_ver.id,
            "content": json.loads(updated_ver.content_json)
        },
        "meta": {"request_id": request_id, "source": "db"},
    }

@router.post("/consultations/{consultation_id}/versions")
def create_consultation_version(
    consultation_id: str,
    payload: ConsultationVersionCreateRequest,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    _require_consultation_access(db, user, consultation_id)
    new_ver = consultation_service.create_version(
        db=db,
        cid=consultation_id,
        content=payload.content,
        change_summary=payload.change_summary,
        actor=user.id,
        expected_version_id=payload.expected_version_id,
        request_id=request_id,
    )
    return {
        "success": True,
        "data": {
            "version_id": new_ver.id,
            "version_number": new_ver.version_number,
            "origin": new_ver.origin,
            "change_summary": new_ver.change_summary
        },
        "meta": {"request_id": request_id, "source": "db"},
    }

@router.get("/consultations/{consultation_id}/versions")
def list_consultation_versions(
    consultation_id: str,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    _require_consultation_access(db, user, consultation_id)
    versions = consultation_service.list_versions(db, consultation_id)
    return {
        "success": True,
        "data": versions,
        "meta": {"request_id": request_id, "source": "db"},
    }

@router.post("/consultations/{consultation_id}/approve/preview")
def preview_approve(
    consultation_id: str,
    payload: ConsultationApproveRequest = Body(default=ConsultationApproveRequest()),
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(require_role("doctor", "admin")),
    request_id: str = Depends(get_request_id),
):
    _require_consultation_access(db, user, consultation_id)
    preview_res = consultation_service.preview_approve(
        db=db,
        cid=consultation_id,
        acknowledged_unedited=payload.acknowledged_unedited
    )
    return {
        "success": True,
        "data": preview_res,
        "meta": {"request_id": request_id, "source": "db"},
    }

@router.post("/consultations/{consultation_id}/approve")
def approve_consultation(
    consultation_id: str,
    payload: ConsultationApproveRequest = Body(default=ConsultationApproveRequest()),
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(require_role("doctor", "admin")),
    request_id: str = Depends(get_request_id),
):
    _require_consultation_access(db, user, consultation_id)
    approval_res = consultation_service.approve(
        db=db,
        cid=consultation_id,
        acknowledged_unedited=payload.acknowledged_unedited,
        approved_by=user.id,
        expected_version_id=payload.expected_version_id,
    )
    return {
        "success": True,
        "data": approval_res,
        "meta": {"request_id": request_id, "source": "db"},
    }
