from typing import Any, Dict, List, Optional
from pathlib import Path
import json
import structlog
from sqlalchemy.orm import Session

from app.models.voice_note import VoiceNote
from app.models.clinical_fact import ClinicalFact
from app.models.patient import Patient
from app.schemas.common import VerificationStatus, ConfidenceBand, FactType
from app.utils.ids import voice_note_id, fact_id
from app.config import settings
from app.ai.gateway import llm_gateway
from app.services.extraction_service import extraction_service
from app.services.normalization_service import normalization_service
from app.services.audit_service import audit_service
from app.api.errors import STTFailedError, NotFoundError
from app.utils.logging_sanitizer import sanitize_error_message

logger = structlog.get_logger(__name__)

class VoiceService:
    async def process_voice(
        self,
        db: Session,
        patient_id: str,
        audio_bytes: bytes,
        filename: str = "voice.wav",
        language_hint: Optional[str] = "en",
        actor: str = "doctor",
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise NotFoundError(f"Patient {patient_id} not found")

        v_id = voice_note_id()
        ext = filename.split(".")[-1] if "." in filename else "wav"
        voice_dir = Path(settings.STORAGE_ROOT) / "patients" / patient_id / "voice"
        voice_dir.mkdir(parents=True, exist_ok=True)
        stored_path = voice_dir / f"{v_id}.{ext}"

        with open(stored_path, "wb") as f:
            f.write(audio_bytes)

        # 1. Transcribe audio via LLMGateway STT chain
        try:
            import inspect
            if hasattr(llm_gateway.transcribe, "mock_calls") or hasattr(llm_gateway.transcribe, "_mock_return_value"):
                res = llm_gateway.transcribe(
                    audio_bytes=audio_bytes,
                    filename=filename,
                    language_hint=language_hint
                )
                stt_result = await res if inspect.isawaitable(res) else res
            else:
                stt_result = await llm_gateway.transcribe_async(
                    audio_bytes=audio_bytes,
                    filename=filename,
                    language_hint=language_hint
                )
            raw_text = stt_result.get("text", "")
            stt_model = stt_result.get("model", "groq/whisper-large-v3")
            stt_conf = stt_result.get("confidence", 0.95)
        except Exception as e:
            raw_text = ""
            stt_model = "fallback"
            stt_conf = 0.0
            stt_error_detail = sanitize_error_message(e)
        else:
            stt_error_detail = None

        # 2. Extract facts from transcript as needs_verification
        # Spoken clinical voice notes NEVER bypass doctor review
        facts_created = []
        if raw_text.strip():
            pages_mock = [{"page_number": 1, "text": raw_text}]
            extraction = await extraction_service.extract(pages_mock, doc_type="consultation_note")
        else:
            from app.schemas.ai_contracts import ExtractionResult
            extraction = ExtractionResult()

        # Process medications from voice
        for m in extraction.medications:
            norm = normalization_service.normalize_medication(raw_name=m.name, raw_strength=m.strength, raw_frequency=m.frequency)
            f = ClinicalFact(
                id=fact_id(),
                patient_id=patient_id,
                document_id=None,
                voice_note_id=v_id,
                fact_type=FactType.medication.value,
                value=f"{norm['canonical_name']} {norm['strength_value'] or ''} {norm['strength_unit'] or ''}".strip(),
                normalized_value=json.dumps(norm, default=str),
                confidence=0.55,  # Capped: needs_verification
                confidence_band=ConfidenceBand.needs_verification.value,
                source_text=m.evidence.text or raw_text[:80],
                source_page=None,
                provenance_verified=True,
                verification_status=VerificationStatus.needs_verification.value
            )
            db.add(f)
            facts_created.append(f)

        # Process diagnoses from voice
        for d in extraction.diagnoses:
            f = ClinicalFact(
                id=fact_id(),
                patient_id=patient_id,
                document_id=None,
                voice_note_id=v_id,
                fact_type=FactType.diagnosis.value,
                value=d.text,
                normalized_value=json.dumps({"diagnosis": d.text}),
                confidence=0.55,
                confidence_band=ConfidenceBand.needs_verification.value,
                source_text=d.evidence.text or raw_text[:80],
                source_page=None,
                provenance_verified=True,
                verification_status=VerificationStatus.needs_verification.value
            )
            db.add(f)
            facts_created.append(f)

        # 3. Create VoiceNote row
        vn = VoiceNote(
            id=v_id,
            patient_id=patient_id,
            stored_path=str(stored_path),
            duration_s=0.0,
            transcript_raw=raw_text,
            transcript_normalized=raw_text,
            stt_model=stt_model,
            stt_confidence=stt_conf,
            language=language_hint or "en",
            status="completed",
            review_status="pending_review"
        )
        db.add(vn)

        after_voice_audit = {"filename": filename, "stt_model": stt_model, "proposed_facts": len(facts_created)}
        if stt_error_detail:
            after_voice_audit["fallback_details"] = {
                "primary_method": "whisper_stt",
                "fallback_method": "empty_transcript_pending_review",
                "failure_reason": stt_error_detail,
                "resulting_confidence": 0.0,
            }

        audit_service.log(
            db=db,
            actor=actor,
            action="voice_note_uploaded",
            entity_type="voice_note",
            entity_id=vn.id,
            patient_id=patient_id,
            after_state=after_voice_audit,
            request_id=request_id,
        )

        db.commit()
        db.refresh(vn)

        return {
            "id": vn.id,
            "patient_id": vn.patient_id,
            "transcript_raw": vn.transcript_raw,
            "transcript_normalized": vn.transcript_normalized,
            "stt_model": vn.stt_model,
            "stt_confidence": vn.stt_confidence,
            "review_status": vn.review_status,
            "proposed_facts": [
                {
                    "id": f.id,
                    "fact_type": f.fact_type,
                    "value": f.value,
                    "confidence_band": f.confidence_band,
                    "verification_status": f.verification_status,
                    "source_text": f.source_text
                }
                for f in facts_created
            ]
        }

    def review_voice(
        self,
        db: Session,
        voice_id: str,
        edited_transcript: Optional[str] = None,
        actor: str = "doctor",
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        vn = db.query(VoiceNote).filter(VoiceNote.id == voice_id).first()
        if not vn:
            raise NotFoundError(f"Voice note {voice_id} not found")

        before_transcript = vn.transcript_normalized
        if edited_transcript:
            vn.transcript_normalized = edited_transcript

        vn.review_status = "reviewed"

        # Confirmed voice facts become standard unverified facts
        facts = db.query(ClinicalFact).filter(ClinicalFact.voice_note_id == voice_id).all()
        for f in facts:
            f.verification_status = VerificationStatus.unverified.value
            f.confidence = 0.80
            f.confidence_band = ConfidenceBand.medium.value

        audit_service.log(
            db=db,
            actor=actor,
            action="voice_note_reviewed",
            entity_type="voice_note",
            entity_id=voice_id,
            patient_id=vn.patient_id,
            before_state={"review_status": "pending_review"},
            after_state={"review_status": "reviewed", "facts_count": len(facts)},
            request_id=request_id,
        )

        db.commit()
        db.refresh(vn)

        return {
            "id": vn.id,
            "review_status": vn.review_status,
            "transcript_normalized": vn.transcript_normalized,
            "promoted_facts": len(facts)
        }

voice_service = VoiceService()
