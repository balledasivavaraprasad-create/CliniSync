from pathlib import Path
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App
    APP_ENV: str = "development"
    APP_NAME: str = "ClinSync"
    API_PREFIX: str = "/api/v1"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: Union[str, List[str]] = "*"
    DEMO_FALLBACKS_ENABLED: bool = True

    # ── Storage / DB
    DATABASE_URL: str = "sqlite:///./clinsync.db"
    STORAGE_ROOT: str = "./storage"
    MAX_UPLOAD_MB: int = 25
    ALLOWED_MIME: str = (
        "application/pdf,image/jpeg,image/png,image/webp,audio/mpeg,audio/wav,audio/mp4,audio/webm"
    )

    # ── Provider keys
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""

    # ── Logical model slots
    LLM_PRIMARY: str = "gemini/gemini-2.5-flash"
    LLM_SECONDARY: str = "gemini/gemini-2.5-pro"
    LLM_FALLBACK_1: str = "groq/llama-3.3-70b-versatile"
    LLM_FALLBACK_2: str = "groq/llama-3.1-8b-instant"
    LLM_JUDGE_PRIMARY: str = "groq/llama-3.3-70b-versatile"
    LLM_JUDGE_FALLBACK: str = "gemini/gemini-2.5-flash"
    VISION_PRIMARY: str = "gemini/gemini-2.5-flash"
    VISION_FALLBACK: str = "gemini/gemini-2.5-pro"
    # Speech-to-text chain. The default primary was `gemini/gemini-2.5-flash`,
    # a text-only model, so the gateway's single-provider attempt always failed
    # and STT degraded to the placeholder transcript on every recording. The
    # chain is walked in order and de-duplicated by `LLMGateway.transcribe`.
    STT_PRIMARY: str = "groq/whisper-large-v3"
    STT_FALLBACK_1: str = "gemini/gemini-2.5-flash"
    STT_FALLBACK_2: str = "groq/whisper-large-v3-turbo"

    # ── Gateway behavior
    LLM_TIMEOUT_S: int = 45
    LLM_MAX_RETRIES: int = 2
    LLM_TEMPERATURE_EXTRACT: float = 0.0
    LLM_TEMPERATURE_SYNTH: float = 0.2
    LLM_COOLDOWN_S: int = 30

    # ── Validation
    VALIDATION_ENABLED: bool = True
    GATE1_MIN_FACT_CONFIDENCE: float = 0.60
    GATE2_MAX_REGEN_ATTEMPTS: int = 2
    PROVENANCE_FUZZY_THRESHOLD: int = 85

    @property
    def allowed_mime_list(self) -> List[str]:
        return [m.strip() for m in self.ALLOWED_MIME.split(",") if m.strip()]

    @property
    def cors_origins_list(self) -> List[str]:
        if isinstance(self.CORS_ORIGINS, list):
            return self.CORS_ORIGINS
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def storage_path(self) -> Path:
        p = Path(self.STORAGE_ROOT)
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
