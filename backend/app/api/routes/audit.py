from typing import List, Optional
import json
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_current_user, CurrentUser
from app.models.audit_log import AuditLog
from app.schemas.common import SuccessResponse

router = APIRouter(tags=["Audit"])


class AuditLogEntry(BaseModel):
    id: str
    timestamp: str
    actor: str
    action: str
    entity_type: str
    entity_id: str
    patient_id: Optional[str]
    before_json: Optional[str]
    after_json: Optional[str]
    request_id: Optional[str]


@router.get("/patients/{patient_id}/audit", response_model=SuccessResponse[List[AuditLogEntry]])
def get_patient_audit_log(
    patient_id: str,
    entity: Optional[str] = Query(None, description="Filter by entity type e.g. consultation, document"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
):
    query = db.query(AuditLog).filter(AuditLog.patient_id == patient_id)
    if entity:
        query = query.filter(AuditLog.entity_type == entity)
    logs = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()

    entries = [
        AuditLogEntry(
            id=log.id,
            timestamp=log.timestamp.isoformat() if log.timestamp else "",
            actor=log.actor,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            patient_id=log.patient_id,
            before_json=log.before_json,
            after_json=log.after_json,
            request_id=log.request_id,
        )
        for log in logs
    ]
    return SuccessResponse(data=entries)
