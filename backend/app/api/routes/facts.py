from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Body, status
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
from app.api.errors import NotFoundError, ForbiddenError, InvalidStateTransitionError
from app.models.clinical_fact import ClinicalFact
from app.models.document import Document
from app.services.audit_service import audit_service

router = APIRouter(tags=["facts"])

class FactPatchRequest(BaseModel):
    verification_status: Optional[str] = None
    semantic_state: Optional[str] = None
    status: Optional[str] = None
    corrected_value: Optional[str] = None
    doctor_note: Optional[str] = None

@router.get("/patients/{patient_id}/facts")
def list_facts(
    patient_id: str,
    type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    min_conf: Optional[float] = Query(None),
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    pid = require_patient_access(patient_id, db, user)
    query = db.query(ClinicalFact).filter(ClinicalFact.patient_id == pid)
    if type:
        query = query.filter(ClinicalFact.fact_type == type)
    if status:
        query = query.filter(
            (ClinicalFact.verification_status == status) |
            (ClinicalFact.verification_status == status.lower()) |
            (ClinicalFact.verification_status == status.upper())
        )
    if min_conf is not None:
        query = query.filter(ClinicalFact.confidence >= min_conf)

    facts = query.order_by(ClinicalFact.created_at.desc()).all()
    results = [
        {
            "id": f.id,
            "patient_id": f.patient_id,
            "document_id": f.document_id,
            "source_document_id": f.document_id,
            "fact_type": f.fact_type,
            "value": f.value,
            "fact_date": f.fact_date.isoformat() if f.fact_date else None,
            "confidence": f.confidence,
            "extraction_confidence": f.confidence,
            "confidence_band": f.confidence_band,
            "confidence_explanation": f.confidence_explanation,
            "source_text": f.source_text,
            "source_page": f.source_page,
            "source_span": f.source_span,
            "source_span_start": f.source_span_start,
            "source_span_end": f.source_span_end,
            "extraction_method": f.extraction_method,
            "provenance_verified": f.provenance_verified,
            "verification_status": f.verification_status,
            "verification_timestamp": f.verification_timestamp,
            "semantic_state": f.semantic_state,
            "status": f.status,
            "created_at": f.created_at.isoformat() if f.created_at else None,
            "updated_at": f.updated_at.isoformat() if f.updated_at else None,
        }
        for f in facts
    ]
    return {
        "success": True,
        "data": results,
        "meta": {"request_id": request_id, "source": "db"},
    }

@router.get("/facts/{fact_id}/evidence")
def get_fact_evidence(
    fact_id: str,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    fact = db.query(ClinicalFact).filter(ClinicalFact.id == fact_id).first()
    if not fact:
        raise NotFoundError(f"Clinical fact {fact_id} not found")

    if not check_patient_authorization(db, user, fact.patient_id):
        raise ForbiddenError(f"User '{user.id}' is not authorized to access fact '{fact_id}'.")

    doc = None
    if fact.document_id:
        doc = db.query(Document).filter(Document.id == fact.document_id).first()

    evidence_data = {
        "fact_id": fact.id,
        "fact_type": fact.fact_type,
        "value": fact.value,
        "confidence": fact.confidence,
        "extraction_confidence": fact.confidence,
        "confidence_band": fact.confidence_band,
        "confidence_explanation": fact.confidence_explanation,
        "extraction_method": fact.extraction_method,
        "provenance_verified": fact.provenance_verified,
        "verification_status": fact.verification_status,
        "verification_timestamp": fact.verification_timestamp,
        "semantic_state": fact.semantic_state,
        "document_id": fact.document_id,
        "source_document_id": fact.document_id,
        "source_page": fact.source_page,
        "source_span": fact.source_span,
        "source_text": fact.source_text,
        "status": fact.status,
        "source": {
            "document_id": fact.document_id,
            "source_document_id": fact.document_id,
            "document_filename": doc.original_filename if doc else None,
            "document_type": doc.document_type if doc else None,
            "document_date": doc.document_date.isoformat() if (doc and doc.document_date) else None,
            "page_number": fact.source_page,
            "source_page": fact.source_page,
            "verbatim_text": fact.source_text,
            "source_text": fact.source_text,
            "span_start": fact.source_span_start,
            "span_end": fact.source_span_end,
            "source_span": fact.source_span,
        }
    }
    return {
        "success": True,
        "data": evidence_data,
        "meta": {"request_id": request_id, "source": "db"},
    }

@router.patch("/facts/{fact_id}")
def patch_fact(
    fact_id: str,
    payload: FactPatchRequest,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    fact = db.query(ClinicalFact).filter(ClinicalFact.id == fact_id).first()
    if not fact:
        raise NotFoundError(f"Clinical fact {fact_id} not found")

    if not check_patient_authorization(db, user, fact.patient_id):
        raise ForbiddenError(f"User '{user.id}' is not authorized to edit fact '{fact_id}'.")

    from datetime import datetime, timezone

    before = {
        "value": fact.value,
        "verification_status": fact.verification_status,
        "semantic_state": fact.semantic_state,
        "status": fact.status,
    }

    target_status = (payload.verification_status or payload.status or payload.semantic_state or "").upper()
    is_approving = target_status in ("APPROVED", "DOCTOR_VERIFIED")

    # 1. Only an authorized doctor or administrator can approve clinical information
    if is_approving and user.role.lower() not in ("doctor", "admin"):
        raise ForbiddenError("Only an authorized doctor or administrator can approve clinical facts.")

    # 2. CONFLICTING -> CURRENT/APPROVED must be rejected until resolved
    is_current_or_active = target_status in ("CURRENT", "DOCUMENTED", "APPROVED", "DOCTOR_VERIFIED", "ACTIVE")
    curr_conflicting = (
        (fact.semantic_state or "").upper() == "CONFLICTING"
        or (fact.status or "").upper() == "CONFLICTING"
        or (fact.verification_status or "").lower() == "conflicting"
    )
    if curr_conflicting and is_current_or_active:
        if not payload.doctor_note and not payload.corrected_value:
            raise InvalidStateTransitionError(
                "CONFLICTING clinical facts cannot transition to CURRENT or APPROVED until resolved with doctor review (doctor_note or corrected_value)."
            )

    # 3. UNVERIFIED -> APPROVED must be rejected unless the defined doctor approval workflow explicitly resolves it
    curr_unverified = (fact.verification_status or "").lower() in ("unverified", "needs_verification")
    if curr_unverified and is_approving:
        if not payload.doctor_note and not payload.corrected_value:
            raise InvalidStateTransitionError(
                "UNVERIFIED facts cannot transition to APPROVED without explicit doctor review or correction (doctor_note or corrected_value)."
            )

    new_status = payload.verification_status or payload.semantic_state or payload.status
    if new_status:
        fact.verification_status = new_status
        if target_status in ("DOCUMENTED", "DOCTOR_VERIFIED", "APPROVED"):
            fact.provenance_verified = True

    if payload.corrected_value:
        fact.value = payload.corrected_value
        fact.provenance_verified = True
        if not new_status:
            fact.verification_status = "doctor_verified"

    audit_service.log(
        db=db,
        actor=user.id,
        action="fact_updated",
        entity_type="clinical_fact",
        entity_id=fact.id,
        patient_id=fact.patient_id,
        before_state=before,
        after_state={
            "value": fact.value,
            "verification_status": fact.verification_status,
            "semantic_state": fact.semantic_state,
            "status": fact.status,
            "note": payload.doctor_note,
        },
        request_id=request_id
    )

    db.commit()
    db.refresh(fact)

    return {
        "success": True,
        "data": {
            "id": fact.id,
            "value": fact.value,
            "verification_status": fact.verification_status,
            "semantic_state": fact.semantic_state,
            "status": fact.status,
        },
        "meta": {"request_id": request_id, "source": "db"},
    }
