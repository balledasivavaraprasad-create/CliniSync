from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, File, Form, UploadFile, status, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import get_db_session, get_current_user, get_request_id, CurrentUser
from app.services.voice_service import voice_service

router = APIRouter(tags=["voice"])

class VoiceReviewRequest(BaseModel):
    edited_transcript: Optional[str] = None

@router.post("/patients/{patient_id}/voice", status_code=status.HTTP_201_CREATED)
async def upload_voice_note(
    patient_id: str,
    file: UploadFile = File(...),
    language_hint: Optional[str] = Form("en"),
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    from app.api.deps import require_patient_id
    pid = require_patient_id(db, patient_id)
    audio_bytes = await file.read()
    res = await voice_service.process_voice(
        db=db,
        patient_id=pid,
        audio_bytes=audio_bytes,
        filename=file.filename or "recording.wav",
        language_hint=language_hint
    )
    return {
        "success": True,
        "data": res,
        "meta": {"request_id": request_id, "source": "stt"},
    }


@router.post("/voice/transcribe", status_code=status.HTTP_201_CREATED)
async def transcribe_voice_legacy(
    file: UploadFile = File(...),
    patient_id: Optional[str] = Form("pat_demo_patient_001"),
    language_hint: Optional[str] = Form("en"),
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    from app.api.deps import require_patient_id
    pid = require_patient_id(db, patient_id or "pat_demo_patient_001")
    audio_bytes = await file.read()
    res = await voice_service.process_voice(
        db=db,
        patient_id=pid,
        audio_bytes=audio_bytes,
        filename=file.filename or "recording.wav",
        language_hint=language_hint
    )
    return {
        "success": True,
        "data": res,
        "meta": {"request_id": request_id, "source": "stt"},
    }


@router.post("/voice/{voice_id}/review")
def review_voice_note(
    voice_id: str,
    payload: VoiceReviewRequest = Body(default=VoiceReviewRequest()),
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    res = voice_service.review_voice(
        db=db,
        voice_id=voice_id,
        edited_transcript=payload.edited_transcript,
        actor=user.id
    )
    return {
        "success": True,
        "data": res,
        "meta": {"request_id": request_id, "source": "db"},
    }
