from typing import Any, Dict, Optional, List, Tuple
from fastapi import APIRouter, Depends, File, Form, UploadFile, status, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import (
    get_db_session,
    get_current_user,
    get_request_id,
    CurrentUser,
    require_patient_access,
    check_patient_authorization,
    require_role,
)
from app.services.voice_service import voice_service
from app.models.voice_note import VoiceNote
from app.api.errors import NotFoundError, ForbiddenError

router = APIRouter(tags=["voice"])

class VoiceReviewRequest(BaseModel):
    edited_transcript: Optional[str] = None

@router.post("/patients/{patient_id}/voice", status_code=status.HTTP_201_CREATED)
async def upload_voice_note(
    patient_id: str,
    file: UploadFile = File(...),
    language_hint: Optional[str] = Form("en"),
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    pid = require_patient_access(patient_id, db, user)
    audio_bytes = await file.read()
    res = await voice_service.process_voice(
        db=db,
        patient_id=pid,
        audio_bytes=audio_bytes,
        filename=file.filename or "recording.wav",
        language_hint=language_hint,
        actor=user.id,
        request_id=request_id,
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
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    pid = require_patient_access(patient_id or "pat_demo_patient_001", db, user)
    audio_bytes = await file.read()
    res = await voice_service.process_voice(
        db=db,
        patient_id=pid,
        audio_bytes=audio_bytes,
        filename=file.filename or "recording.wav",
        language_hint=language_hint,
        actor=user.id,
        request_id=request_id,
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
    user: CurrentUser = Depends(require_role("doctor", "admin")),
    request_id: str = Depends(get_request_id),
):
    vn = db.query(VoiceNote).filter(VoiceNote.id == voice_id).first()
    if not vn:
        raise NotFoundError(f"Voice note {voice_id} not found")

    if not check_patient_authorization(db, user, vn.patient_id):
        raise ForbiddenError(f"User '{user.id}' is not authorized to review voice note for this patient.")

    res = voice_service.review_voice(
        db=db,
        voice_id=voice_id,
        edited_transcript=payload.edited_transcript,
        actor=user.id,
        request_id=request_id,
    )
    return {
        "success": True,
        "data": res,
        "meta": {"request_id": request_id, "source": "db"},
    }


# ── ElevenLabs Voice Consultation & Adaptive Intelligence Engine ────────────
import os
import base64
import json
import urllib.request
from fastapi.responses import Response

class DoctorSpeechRequest(BaseModel):
    text: str
    voice_id: Optional[str] = None

class DoctorTurnRequest(BaseModel):
    patient_input: Optional[str] = None
    user_input: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = []
    chat_history: Optional[List[Dict[str, Any]]] = []
    chart: Optional[Dict[str, Any]] = None
    current_chart: Optional[Dict[str, Any]] = None
    patient_name: Optional[str] = "Patient"
    synthesize_voice: Optional[bool] = True


def _call_elevenlabs_tts(text: str, voice_id: Optional[str] = None) -> Optional[bytes]:
    """Synthesize human physician voice via ElevenLabs using user's configured API key."""
    api_key = (os.getenv("ELEVENLABS_API_KEY") or getattr(settings, "ELEVENLABS_API_KEY", "") or "").strip()

    # Default to Adam (warm, natural physician voice) or Sarah (empathetic clinician)
    target_voice = voice_id or os.getenv("ELEVENLABS_VOICE_ID") or getattr(settings, "ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB") or "pNInz6obpgDQGcFmaJgB"
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{target_voice}"
    payload = json.dumps({
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.55,
            "similarity_boost": 0.85
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read()
    except Exception as exc:
        logger.warning("elevenlabs_tts_failed", error=str(exc))
        return None


@router.post("/voice/consult-doctor-speech")
def consult_doctor_speech(payload: DoctorSpeechRequest):
    """Generate high-fidelity human doctor voice using ElevenLabs."""
    audio_bytes = _call_elevenlabs_tts(payload.text, payload.voice_id)
    if not audio_bytes:
        return Response(status_code=502, content="ElevenLabs TTS synthesis failed")
    return Response(content=audio_bytes, media_type="audio/mpeg")


@router.post("/voice/consult-doctor-stt")
async def consult_doctor_stt(file: UploadFile = File(...)):
    """Transcribe patient speech via ElevenLabs Scribe STT."""
    api_key = (os.getenv("ELEVENLABS_API_KEY") or getattr(settings, "ELEVENLABS_API_KEY", "") or "").strip()

    audio_bytes = await file.read()
    
    # Boundary multipart request
    boundary = "----ClinSyncBoundary" + os.urandom(8).hex()
    body = bytearray()
    
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(b'Content-Disposition: form-data; name="model_id"\r\n\r\n')
    body.extend(b'scribe_v1\r\n')
    
    filename = file.filename or "speech.wav"
    content_type = file.content_type or "audio/wav"
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode("utf-8"))
    body.extend(f'Content-Type: {content_type}\r\n\r\n'.encode("utf-8"))
    body.extend(audio_bytes)
    body.extend(b'\r\n')
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/speech-to-text",
        data=bytes(body),
        headers={
            "xi-api-key": api_key,
            "Content-Type": f"multipart/form-data; boundary={boundary}"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            transcript = data.get("text", "")
            return {"success": True, "transcript": transcript}
    except Exception as exc:
        logger.warning("elevenlabs_stt_failed", error=str(exc))
        return {"success": False, "error": str(exc), "transcript": ""}


@router.post("/voice/consult-doctor-turn")
def consult_doctor_turn(payload: DoctorTurnRequest):
    """
    Adaptive Intelligence Clinical Turn:
    Actively queries and collects comprehensive patient intake details (symptoms, duration, severity, medications, allergies).
    Answers with natural human doctor tone and synthesizes speech using ElevenLabs.
    """
    inp = (payload.user_input or payload.patient_input or "").strip()
    chart = dict(payload.current_chart or payload.chart or {})
    inp_lower = inp.lower()

    # Dynamic extraction of clinical details from patient turn
    if not chart.get("chief_complaint") or len(chart.get("chief_complaint", "")) < 3:
        chart["chief_complaint"] = inp
    else:
        # Check if duration/onset is mentioned
        if any(w in inp_lower for w in ["day", "week", "month", "hour", "yesterday", "since", "morning"]):
            chart["duration"] = chart.get("duration") or inp
        # Check for severity / pain scale
        import re
        scale_match = re.search(r"\b([0-9]|10)\b", inp)
        if scale_match and any(w in inp_lower for w in ["scale", "pain", "rate", "/10", "out of 10", "level"]):
            chart["severity"] = f"{scale_match.group(1)} / 10 Pain Scale"
        elif any(w in inp_lower for w in ["mild", "moderate", "severe", "unbearable", "sharp", "dull"]):
            chart["severity"] = chart.get("severity") or inp
        # Check for medications
        if any(w in inp_lower for w in ["taking", "med", "pill", "tablet", "prescrib", "mg", "metformin", "aspirin", "tylenol", "advil", "insulin", "none", "no meds"]):
            chart["medications"] = chart.get("medications") or (inp if "none" not in inp_lower else "No active prescription medications")
        # Check for allergies
        if any(w in inp_lower for w in ["allergic", "allergy", "penicillin", "sulfa", "rash", "reaction", "no allergy", "nkda"]):
            chart["allergies"] = chart.get("allergies") or (inp if "no" not in inp_lower else "No known drug allergies (NKDA)")

    # Adaptive Clinical Inquiry Decision Tree
    reply_text = ""
    if not chart.get("duration"):
        reply_text = f"Thank you for sharing that with me. To ensure your doctor has a clear picture: How long have you been experiencing these symptoms, and did they come on suddenly or gradually?"
    elif not chart.get("severity"):
        reply_text = f"Understood. On a scale of 1 to 10, with 10 being the most intense, how severe would you rate your discomfort right now, and how would you describe the sensation—like sharp, dull, throbbing, or burning?"
    elif not chart.get("medications"):
        reply_text = f"Got it. Are you currently taking any regular medications, over-the-counter painkillers, or supplements? If none, simply say none."
    elif not chart.get("allergies"):
        reply_text = f"Thank you. Do you have any known allergies to medications, such as Penicillin or NSAIDs, or any foods?"
    elif not chart.get("past_history"):
        chart["past_history"] = "Reviewed in intake"
        reply_text = f"Lastly, do you have any pre-existing medical conditions, such as diabetes, high blood pressure, or asthma, or a family history of heart disease?"
    else:
        reply_text = f"Thank you very much. I have documented your symptoms, duration ({chart.get('duration')}), severity ({chart.get('severity')}), medications, and allergy profile into your St. Jude Hospital medical record. Your clinical brief is now fully prepared for your physician consultation."

    # Synthesize ElevenLabs voice if requested
    base64_audio = None
    if payload.synthesize_voice:
        audio_raw = _call_elevenlabs_tts(reply_text)
        if audio_raw:
            base64_audio = base64.b64encode(audio_raw).decode("utf-8")

    return {
        "success": True,
        "reply": reply_text,
        "updated_chart": chart,
        "audio_base64": base64_audio,
        "voice_engine": "ElevenLabs (Adam - Natural Human Physician)",
    }

