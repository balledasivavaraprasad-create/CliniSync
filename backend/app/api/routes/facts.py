from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Body, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import get_db_session, get_current_user, get_request_id, CurrentUser, require_patient_id
from app.api.errors import NotFoundError
from app.models.clinical_fact import ClinicalFact
from app.models.document import Document
from app.services.audit_service import audit_service

router = APIRouter(tags=["facts"])

class FactPatchRequest(BaseModel):
    verification_status: Optional[str] = None
    corrected_value: Optional[str] = None
    doctor_note: Optional[str] = None

@router.get("/patients/{patient_id}/facts")
def list_facts(
    patient_id: str,
    type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    min_conf: Optional[float] = Query(None),
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    patient_id = require_patient_id(db, patient_id)
    query = db.query(ClinicalFact).filter(ClinicalFact.patient_id == patient_id)
    if type:
        query = query.filter(ClinicalFact.fact_type == type)
    if status:
        query = query.filter(ClinicalFact.verification_status == status)
    if min_conf is not None:
        query = query.filter(ClinicalFact.confidence >= min_conf)

    facts = query.order_by(ClinicalFact.created_at.desc()).all()
    results = [
        {
            "id": f.id,
            "patient_id": f.patient_id,
            "document_id": f.document_id,
            "fact_type": f.fact_type,
            "value": f.value,
            "fact_date": f.fact_date.isoformat() if f.fact_date else None,
            "confidence": f.confidence,
            "confidence_band": f.confidence_band,
            "source_text": f.source_text,
            "source_page": f.source_page,
            "provenance_verified": f.provenance_verified,
            "verification_status": f.verification_status,
            "created_at": f.created_at.isoformat() if f.created_at else None,
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
    request_id: str = Depends(get_request_id),
):
    fact = db.query(ClinicalFact).filter(ClinicalFact.id == fact_id).first()
    if not fact:
        raise NotFoundError(f"Clinical fact {fact_id} not found")

    doc = None
    if fact.document_id:
        doc = db.query(Document).filter(Document.id == fact.document_id).first()

    evidence_data = {
        "fact_id": fact.id,
        "fact_type": fact.fact_type,
        "value": fact.value,
        "confidence": fact.confidence,
        "confidence_band": fact.confidence_band,
        "provenance_verified": fact.provenance_verified,
        "verification_status": fact.verification_status,
        "source": {
            "document_id": fact.document_id,
            "document_filename": doc.original_filename if doc else None,
            "document_type": doc.document_type if doc else None,
            "document_date": doc.document_date.isoformat() if (doc and doc.document_date) else None,
            "page_number": fact.source_page,
            "verbatim_text": fact.source_text,
            "span_start": fact.source_span_start,
            "span_end": fact.source_span_end,
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

    before = {"value": fact.value, "verification_status": fact.verification_status}

    if payload.verification_status:
        fact.verification_status = payload.verification_status
    if payload.corrected_value:
        fact.value = payload.corrected_value

    audit_service.log(
        db=db,
        actor=user.id,
        action="fact_updated",
        entity_type="clinical_fact",
        entity_id=fact.id,
        patient_id=fact.patient_id,
        before_state=before,
        after_state={"value": fact.value, "verification_status": fact.verification_status, "note": payload.doctor_note},
        request_id=request_id
    )

    db.commit()
    db.refresh(fact)

    return {
        "success": True,
        "data": {
            "id": fact.id,
            "value": fact.value,
            "verification_status": fact.verification_status
        },
        "meta": {"request_id": request_id, "source": "db"},
    }
