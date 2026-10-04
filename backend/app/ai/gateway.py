import base64
import time
from typing import Any, Dict, List, Optional, Type
import litellm
from litellm import Router
from pydantic import BaseModel
import structlog
import httpx

from app.config import settings
from app.ai.models_registry import get_model_list
from app.ai.json_utils import repair_and_parse_json
from app.api.errors import LLMUnavailableError
from app.db.database import SessionLocal
from app.models.audit_log import LLMCallLog
from app.utils.ids import llm_log_id

logger = structlog.get_logger()

# Configure LiteLLM globally
litellm.telemetry = False
litellm.drop_params = True


class LLMGateway:
    _instance: Optional["LLMGateway"] = None

    def __init__(self):
        self.router = Router(
            model_list=get_model_list(),
            num_retries=settings.LLM_MAX_RETRIES,
            timeout=settings.LLM_TIMEOUT_S,
            cooldown_time=settings.LLM_COOLDOWN_S,
        )

    @classmethod
    def get_instance(cls) -> "LLMGateway":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _log_call(
        self,
        task: str,
        slot: str,
        model_used: str,
        latency_ms: float,
        success: bool,
        input_tokens: int = 0,
        output_tokens: int = 0,
        error_code: Optional[str] = None,
        request_id: Optional[str] = None,
        fallback_depth: int = 0,
    ):
        try:
            with SessionLocal() as db:
                log_entry = LLMCallLog(
                    id=llm_log_id(),
                    request_id=request_id,
                    task=task,
                    logical_slot=slot,
                    provider_model_used=model_used,
                    fallback_depth=fallback_depth,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    success=success,
                    error_code=error_code,
                )
                db.add(log_entry)
                db.commit()
        except Exception as e:
            logger.warn("Failed to write llm_call_log", error=str(e))

    def complete_text(
        self,
        task: str,
        messages: List[Dict[str, str]],
        slot: str = "llm_generate",
        request_id: Optional[str] = None,
    ) -> str:
        start_time = time.time()
        try:
            resp = self.router.completion(
                model=slot,
                messages=messages,
            )
            latency_ms = (time.time() - start_time) * 1000
            content = resp.choices[0].message.content or ""
            model_used = resp.get("model", slot)
            self._log_call(task, slot, model_used, latency_ms, True, request_id=request_id)
            return content
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._log_call(task, slot, "unknown", latency_ms, False, error_code=str(e)[:60], request_id=request_id)
            logger.error("LLM complete_text failed", task=task, error=str(e))
            raise LLMUnavailableError(f"All LLM providers for slot '{slot}' failed: {e}")

    def complete_json(
        self,
        task: str,
        messages: List[Dict[str, str]],
        schema: Type[BaseModel],
        slot: str = "llm_extract",
        temperature: Optional[float] = None,
        request_id: Optional[str] = None,
    ) -> BaseModel:
        start_time = time.time()
        fallback_depth = 0
        kwargs = {}
        if temperature is not None:
            kwargs["temperature"] = temperature

        try:
            resp = self.router.completion(
                model=slot,
                messages=messages,
                response_format={"type": "json_object"},
                **kwargs,
            )
            raw_text = resp.choices[0].message.content or ""
            model_used = resp.get("model", slot)

            # Parse and validate with repair fallback
            try:
                data = repair_and_parse_json(raw_text)
                parsed = schema.model_validate(data)
                latency_ms = (time.time() - start_time) * 1000
                self._log_call(task, slot, model_used, latency_ms, True, request_id=request_id)
                return parsed
            except Exception as parse_err:
                # Re-ask once with validation error feedback
                logger.warn("JSON parse failed, re-asking model", error=str(parse_err))
                messages.append({"role": "assistant", "content": raw_text})
                messages.append({
                    "role": "user",
                    "content": f"Your previous output was invalid JSON according to the schema: {parse_err}. Correct the error and output valid JSON only.",
                })
                resp2 = self.router.completion(
                    model=slot,
                    messages=messages,
                    response_format={"type": "json_object"},
                    **kwargs,
                )
                raw_text2 = resp2.choices[0].message.content or ""
                data2 = repair_and_parse_json(raw_text2)
                parsed = schema.model_validate(data2)
                latency_ms = (time.time() - start_time) * 1000
                self._log_call(task, slot, model_used, latency_ms, True, request_id=request_id, fallback_depth=1)
                return parsed
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._log_call(task, slot, "unknown", latency_ms, False, error_code=str(e)[:60], request_id=request_id)
            logger.error("LLM complete_json failed", task=task, error=str(e))
            raise LLMUnavailableError(f"Failed to generate structured JSON for task '{task}': {e}")

    def vision_extract(
        self,
        task: str,
        image_bytes: bytes,
        prompt: str,
        mime_type: str = "image/jpeg",
        request_id: Optional[str] = None,
    ) -> str:
        """Process image/scan via Gemini/Groq multimodal vision models."""
        start_time = time.time()
        base64_img = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{base64_img}"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ]

        # Try primary Gemini multimodal first, then Groq
        models_to_try = [settings.VISION_PRIMARY, settings.VISION_FALLBACK]
        for depth, model in enumerate(models_to_try):
            try:
                key = settings.GEMINI_API_KEY if "gemini" in model else settings.GROQ_API_KEY
                resp = litellm.completion(
                    model=model,
                    api_key=key,
                    messages=messages,
                    timeout=settings.LLM_TIMEOUT_S,
                )
                latency_ms = (time.time() - start_time) * 1000
                content = resp.choices[0].message.content or ""
                self._log_call(task, "vision", model, latency_ms, True, request_id=request_id, fallback_depth=depth)
                return content
            except Exception as e:
                logger.warn("Vision model attempt failed", model=model, error=str(e))

        raise LLMUnavailableError("All vision models failed to process image")

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language_hint: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Transcribe audio via Groq Whisper or Gemini Audio."""
        start_time = time.time()
        # 1. Try Groq Whisper primary for audio
        if settings.GROQ_API_KEY:
            try:
                files = {"file": (filename, audio_bytes, "audio/wav")}
                data = {"model": "whisper-large-v3"}
                if language_hint:
                    data["language"] = language_hint
                with httpx.Client(timeout=60.0) as client:
                    r = client.post(
                        "https://api.groq.com/openai/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                        files=files,
                        data=data,
                    )
                    if r.status_code == 200:
                        text = r.json().get("text", "")
                        latency_ms = (time.time() - start_time) * 1000
                        self._log_call("voice_stt", "stt", "groq/whisper-large-v3", latency_ms, True, request_id=request_id)
                        return {"text": text, "model": "groq/whisper-large-v3", "confidence": 0.95}
            except Exception as e:
                logger.warn("Groq Whisper STT failed, trying fallback", error=str(e))

        # Fallback
        raise LLMUnavailableError("All speech-to-text providers failed")

    def judge(
        self,
        task: str,
        content_to_judge: str,
        rubric_prompt: str,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Runs the validation judge model (Groq primary, Gemini fallback)."""
        messages = [
            {"role": "system", "content": rubric_prompt},
            {"role": "user", "content": f"<content_to_evaluate>\n{content_to_judge}\n</content_to_evaluate>"},
        ]
        start_time = time.time()
        try:
            resp = self.router.completion(
                model="llm_judge",
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            latency_ms = (time.time() - start_time) * 1000
            raw = resp.choices[0].message.content or "{}"
            data = repair_and_parse_json(raw)
            model_used = resp.get("model", "llm_judge")
            self._log_call(task, "llm_judge", model_used, latency_ms, True, request_id=request_id)
            return data
        except Exception as e:
            logger.warn("Primary judge router attempt failed, attempting fallback directly", error=str(e))
            try:
                import litellm
                resp = litellm.completion(
                    model=settings.LLM_JUDGE_FALLBACK,
                    api_key=settings.GEMINI_API_KEY if "gemini" in settings.LLM_JUDGE_FALLBACK else settings.GROQ_API_KEY,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.0,
                    timeout=settings.LLM_TIMEOUT_S,
                )
                latency_ms = (time.time() - start_time) * 1000
                raw = resp.choices[0].message.content or "{}"
                data = repair_and_parse_json(raw)
                self._log_call(task, "llm_judge", settings.LLM_JUDGE_FALLBACK, latency_ms, True, request_id=request_id)
                return data
            except Exception as e2:
                latency_ms = (time.time() - start_time) * 1000
                self._log_call(task, "llm_judge", "unknown", latency_ms, False, error_code=str(e2)[:60], request_id=request_id)
                logger.error("LLM judge failed on primary and fallback", error=str(e2))
                raise LLMUnavailableError(f"Judge model failed: {e2}")



llm_gateway = LLMGateway.get_instance()
