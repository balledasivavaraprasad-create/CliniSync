from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_request_id, get_current_user, CurrentUser, require_patient_access
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
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    pid = require_patient_access(patient_id, db, user)
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
