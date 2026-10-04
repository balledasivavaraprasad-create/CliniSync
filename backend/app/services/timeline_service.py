from typing import Any, Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
import json
import structlog

from app.db.database import get_db_context
from app.models.timeline_event import TimelineEvent
from app.models.clinical_fact import ClinicalFact

logger = structlog.get_logger(__name__)

class TimelineService:
    @staticmethod
    def get_timeline(
        db: Session,
        patient_id: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        query = db.query(TimelineEvent).filter(TimelineEvent.patient_id == patient_id)

        if event_type:
            query = query.filter(TimelineEvent.event_type == event_type)

        if from_date:
            try:
                dt_from = datetime.fromisoformat(from_date)
                query = query.filter(TimelineEvent.event_date >= dt_from)
            except Exception:
                pass

        if to_date:
            try:
                dt_to = datetime.fromisoformat(to_date)
                query = query.filter(TimelineEvent.event_date <= dt_to)
            except Exception:
                pass

        # Sort chronological descending (latest first)
        events = query.order_by(desc(TimelineEvent.event_date)).limit(limit).all()

        results = []
        for e in events:
            fact_ids = []
            try:
                if e.related_fact_ids:
                    fact_ids = json.loads(e.related_fact_ids)
            except Exception:
                pass

            results.append({
                "id": e.id,
                "patient_id": e.patient_id,
                "event_type": e.event_type,
                "event_date": e.event_date.isoformat() if e.event_date else None,
                "date_precision": e.date_precision,
                "title": e.title,
                "summary": e.summary,
                "related_fact_ids": fact_ids,
                "source_document_id": e.source_document_id,
                "sort_key": e.sort_key,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            })

        return results

timeline_service = TimelineService()
