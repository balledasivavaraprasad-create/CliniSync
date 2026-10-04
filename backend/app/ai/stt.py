from typing import Any, Dict, Optional
from app.ai.gateway import LLMGateway


def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "audio.wav",
    language_hint: Optional[str] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    gateway = LLMGateway.get_instance()
    return gateway.transcribe(
        audio_bytes=audio_bytes,
        filename=filename,
        language_hint=language_hint,
        request_id=request_id,
    )
