from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
import json
import structlog

from app.models.clinical_memory import ClinicalMemory

logger = structlog.get_logger(__name__)

class MemoryService:
    @staticmethod
    def get_patient_memory(db: Session, patient_id: str, verified_only: bool = True) -> List[Dict[str, Any]]:
        query = db.query(ClinicalMemory).filter(ClinicalMemory.patient_id == patient_id)
        if verified_only:
            query = query.filter(ClinicalMemory.verified == True)

        memories = query.order_by(desc(ClinicalMemory.created_at)).all()
        results = []
        for m in memories:
            results.append({
                "id": m.id,
                "memory_type": m.memory_type,
                "content": json.loads(m.content_json) if m.content_json else {},
                "source_consultation_id": m.source_consultation_id,
                "verified": m.verified,
                "validation_report_id": m.validation_report_id,
                "created_at": m.created_at.isoformat() if m.created_at else None
            })
        return results

    @staticmethod
    def get_memory_history(db: Session, patient_id: str) -> List[Dict[str, Any]]:
        return MemoryService.get_patient_memory(db, patient_id, verified_only=False)

memory_service = MemoryService()
