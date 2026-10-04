from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_request_id
from app.services.timeline_service import timeline_service

router = APIRouter(tags=["timeline"])

@router.get("/patients/{patient_id}/timeline")
def get_timeline(
    patient_id: str,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    type: Optional[str] = Query(None),
    limit: int = Query(100),
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    from app.api.deps import resolve_patient_id
    pid = resolve_patient_id(patient_id)
    events = timeline_service.get_timeline(
        db=db,
        patient_id=pid,
        from_date=from_date,
        to_date=to_date,
        event_type=type,
        limit=limit
    )
    return {
        "success": True,
        "data": events,
        "meta": {"request_id": request_id, "source": "db"},
    }
