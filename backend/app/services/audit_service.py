import json
from typing import Any, Optional
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog


def write_audit(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: str,
    actor: str = "doctor",
    patient_id: Optional[str] = None,
    before: Optional[Any] = None,
    after: Optional[Any] = None,
    request_id: Optional[str] = None,
    ip: Optional[str] = None,
) -> AuditLog:
    """Enforces INV-9: Every state-changing action writes an audit_log row."""
    before_json = json.dumps(before) if before is not None else None
    after_json = json.dumps(after) if after is not None else None

    entry = AuditLog(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        patient_id=patient_id,
        before_json=before_json,
        after_json=after_json,
        request_id=request_id,
        ip=ip,
    )
    db.add(entry)
    db.flush()
    return entry


class AuditService:
    @staticmethod
    def log(
        db: Session,
        action: str,
        entity_type: str,
        entity_id: str,
        actor: str = "system",
        patient_id: Optional[str] = None,
        before_state: Optional[Any] = None,
        after_state: Optional[Any] = None,
        request_id: Optional[str] = None,
        ip: Optional[str] = None,
    ) -> AuditLog:
        return write_audit(
            db=db,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            patient_id=patient_id,
            before=before_state,
            after=after_state,
            request_id=request_id,
            ip=ip,
        )


audit_service = AuditService()
