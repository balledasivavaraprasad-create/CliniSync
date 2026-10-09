from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session
import json
import hashlib

from app.api.deps import (
    get_db_session,
    get_request_id,
    get_current_user,
    CurrentUser,
    require_patient_access,
    check_patient_authorization,
    require_role,
)
from app.services.memory_service import memory_service
from app.models.clinical_memory import ClinicalMemory
from app.utils.ids import clinical_memory_id
from app.api.errors import NotFoundError, ForbiddenError, InvalidStateTransitionError

router = APIRouter(tags=["memory"])

@router.get("/patients/{patient_id}/memory")
@router.get("/patients/{patient_id}/memories")
def get_verified_memory(
    patient_id: str,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    pid = require_patient_access(patient_id, db, user)
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
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    pid = require_patient_access(patient_id, db, user)
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
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    pid = require_patient_access(patient_id, db, user)
    memories = memory_service.get_patient_memory(db=db, patient_id=pid, verified_only=False)
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
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    pid = require_patient_access(patient_id, db, user)

    mem_payload = {
        "content": payload.get("content", ""),
        "memory_state": "UNVERIFIED",
        "semantic_state": "UNVERIFIED",
        "provenance": {
            "proposed_by": user.id,
            "evidence_reference": payload.get("evidence"),
        }
    }
    mem = ClinicalMemory(
        id=clinical_memory_id(),
        patient_id=pid,
        memory_type=payload.get("memory_type", "plan_note"),
        content_json=json.dumps(mem_payload),
        verified=False,
    )
    db.add(mem)

    from app.services.audit_service import audit_service
    audit_service.log(
        db=db,
        actor=user.id,
        action="clinical_memory_proposed",
        entity_type="clinical_memory",
        entity_id=mem.id,
        patient_id=pid,
        after_state={"memory_type": mem.memory_type, "verified": False},
        request_id=request_id,
    )

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
    payload_req: Optional[dict] = Body(default=None),
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(require_role("doctor", "admin")),
    request_id: str = Depends(get_request_id),
):
    mem = db.query(ClinicalMemory).filter(ClinicalMemory.id == proposal_id).first()
    if not mem:
        raise NotFoundError(f"Memory proposal {proposal_id} not found")

    if not check_patient_authorization(db, user, mem.patient_id):
        raise ForbiddenError(f"User '{user.id}' is not authorized to approve memory for this patient.")

    payload = mem.payload
    req = payload_req or {}

    # 1. AI_GENERATED -> MEMORY must be rejected without explicit doctor review
    mem_origin = (payload.get("origin") or payload.get("memory_state") or "").upper()
    if mem_origin == "AI_GENERATED":
        doctor_reviewed = payload.get("doctor_reviewed") or req.get("doctor_reviewed") or req.get("doctor_edited")
        if not doctor_reviewed:
            raise InvalidStateTransitionError(
                "AI_GENERATED clinical memory proposals cannot transition directly to MEMORY without doctor review."
            )

    # 2. CONFLICTING -> CURRENT must be rejected until resolved
    is_conflicting = (
        (payload.get("memory_state") or "").upper() == "CONFLICTING"
        or (payload.get("semantic_state") or "").upper() == "CONFLICTING"
    )
    if is_conflicting:
        is_resolved = payload.get("resolved") or req.get("resolved") or req.get("doctor_note")
        if not is_resolved:
            raise InvalidStateTransitionError(
                "CONFLICTING clinical memory cannot transition to CURRENT until resolved with doctor review."
            )

    before_ver = mem.verified
    mem.verified = True

    # Compute content hash
    from datetime import datetime, timezone
    now_dt = datetime.now(timezone.utc)
    raw_content = payload.get("content", "")
    content_hash = hashlib.sha256(json.dumps(raw_content, sort_keys=True).encode("utf-8")).hexdigest()

    # Update payload with approving doctor provenance and CURRENT lifecycle state
    prov = payload.get("provenance") or {}
    prov["doctor_id"] = user.id
    prov["approved_by"] = user.id
    prov["approved_at"] = now_dt.isoformat()
    prov["version_id"] = mem.id
    prov["content_hash"] = content_hash
    if req.get("doctor_note"):
        prov["doctor_note"] = req["doctor_note"]

    payload["provenance"] = prov
    payload["semantic_state"] = "DOCUMENTED"
    payload["memory_state"] = "CURRENT"
    mem.content_json = json.dumps(payload)

    from app.services.audit_service import audit_service
    audit_service.log(
        db=db,
        actor=user.id,
        action="clinical_memory_approved",
        entity_type="clinical_memory",
        entity_id=mem.id,
        patient_id=mem.patient_id,
        before_state={"verified": before_ver},
        after_state={
            "verified": True,
            "memory_state": "CURRENT",
            "doctor_id": user.id,
            "version_id": mem.id,
            "approval_timestamp": now_dt.isoformat(),
            "content_hash": content_hash,
        },
        request_id=request_id,
    )

    db.commit()
    return {
        "success": True,
        "data": {
            "id": proposal_id,
            "version_id": mem.id,
            "doctor_id": user.id,
            "approval_timestamp": now_dt.isoformat(),
            "content_hash": content_hash,
            "memory_state": "CURRENT",
            "verified": True,
        },
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.post("/memories/{proposal_id}/reject")
def reject_proposed_memory(
    proposal_id: str,
    payload: Optional[dict] = None,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(require_role("doctor", "admin")),
    request_id: str = Depends(get_request_id),
):
    mem = db.query(ClinicalMemory).filter(ClinicalMemory.id == proposal_id).first()
    if not mem:
        raise NotFoundError(f"Memory proposal {proposal_id} not found")

    if not check_patient_authorization(db, user, mem.patient_id):
        raise ForbiddenError(f"User '{user.id}' is not authorized to reject memory for this patient.")

    patient_id = mem.patient_id
    from app.services.audit_service import audit_service
    audit_service.log(
        db=db,
        actor=user.id,
        action="clinical_memory_rejected",
        entity_type="clinical_memory",
        entity_id=proposal_id,
        patient_id=patient_id,
        before_state={"memory_type": mem.memory_type, "verified": mem.verified},
        after_state={"status": "rejected"},
        request_id=request_id,
    )

    db.delete(mem)
    db.commit()
    return {
        "success": True,
        "data": {"id": proposal_id, "status": "rejected"},
        "meta": {"request_id": request_id, "source": "db"},
    }
