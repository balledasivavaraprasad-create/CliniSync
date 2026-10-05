from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_request_id
from app.services.memory_service import memory_service

router = APIRouter(tags=["memory"])

@router.get("/patients/{patient_id}/memory")
@router.get("/patients/{patient_id}/memories")
def get_verified_memory(
    patient_id: str,
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    from app.api.deps import require_patient_id
    pid = require_patient_id(db, patient_id)
    memories = memory_service.get_patient_memory(db=db, patient_id=pid, verified_only=True)
    return {
        "success": True,
        "data": memories,
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.get("/patients/{patient_id}/memory/history")
@router.get("/patients/{patient_id}/memories/history")
def get_memory_history(
    patient_id: str,
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    from app.api.deps import require_patient_id
    pid = require_patient_id(db, patient_id)
    memories = memory_service.get_memory_history(db=db, patient_id=pid)
    return {
        "success": True,
        "data": memories,
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.get("/patients/{patient_id}/memories/review-queue")
def get_memory_review_queue(
    patient_id: str,
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    from app.api.deps import require_patient_id
    pid = require_patient_id(db, patient_id)
    memories = memory_service.get_patient_memory(db=db, patient_id=pid, verified_only=False)
    # Filter for unverified or pending review
    queue = [m for m in memories if not m.get("verified")]
    return {
        "success": True,
        "data": queue,
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.post("/patients/{patient_id}/memories/proposals")
def propose_memory(
    patient_id: str,
    payload: dict,
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    from app.api.deps import require_patient_id
    from app.models.clinical_memory import ClinicalMemory
    from app.utils.ids import clinical_memory_id
    import json
    pid = require_patient_id(db, patient_id)

    mem = ClinicalMemory(
        id=clinical_memory_id(),
        patient_id=pid,
        memory_type=payload.get("memory_type", "plan_note"),
        content_json=json.dumps({"content": payload.get("content", "")}),
        verified=False,
    )
    db.add(mem)
    db.commit()
    db.refresh(mem)

    return {
        "success": True,
        "data": {"id": mem.id, "patient_id": mem.patient_id, "status": "proposed"},
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.post("/memories/{proposal_id}/approve")
def approve_proposed_memory(
    proposal_id: str,
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    from app.models.clinical_memory import ClinicalMemory
    mem = db.query(ClinicalMemory).filter(ClinicalMemory.id == proposal_id).first()
    if mem:
        mem.verified = True
        db.commit()
    return {
        "success": True,
        "data": {"id": proposal_id, "verified": True},
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.post("/memories/{proposal_id}/reject")
def reject_proposed_memory(
    proposal_id: str,
    payload: dict,
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    from app.models.clinical_memory import ClinicalMemory
    mem = db.query(ClinicalMemory).filter(ClinicalMemory.id == proposal_id).first()
    if mem:
        db.delete(mem)
        db.commit()
    return {
        "success": True,
        "data": {"id": proposal_id, "status": "rejected"},
        "meta": {"request_id": request_id, "source": "db"},
    }

