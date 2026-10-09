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

    # ── Auth Security
    JWT_SECRET_KEY: str = Field(default="clinsync-default-insecure-dev-secret-key-change-me", validation_alias="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    AUTH_DEMO_FALLBACK_ENABLED: bool = True  # Isolated behind explicit flag for dev/tests
    ALLOW_DEBUG_PHI_LOGGING: bool = False  # Disabled by default: opt-in only for local debugging

    # ── Storage / DB
    DATABASE_URL: str = "sqlite:///./clinsync.db"
    STORAGE_ROOT: str = "./storage"
    MAX_UPLOAD_MB: int = 25
    ALLOWED_MIME: str = (
        "application/pdf,image/jpeg,image/png,image/webp,audio/mpeg,audio/wav,audio/mp4,audio/webm,"
        "text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
        "application/vnd.openxmlformats-officedocument.presentationml.presentation,"
        "application/msword,application/vnd.ms-powerpoint,application/zip,application/x-ole-storage"
    )
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

    # ── Provider keys
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = "pNInz6obpgDQGcFmaJgB"

    # ── SMTP Email Dispatcher (for 2FA Email OTP)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""

    # ── MongoDB Cloud Database
    MONGODB_URI: str = ""
    MONGODB_DB_NAME: str = "clinisync_db"

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

    # ── Source Authority & Conflict Priority Hierarchy
    # Configurable ranking from highest to lowest authority:
    # 1. Doctor-approved consultation information
    # 2. Doctor-entered information
    # 3. Official clinical document
    # 4. Laboratory report
    # 5. Prescription
    # 6. Patient-reported information
    # 7. AI inference
    SOURCE_PRIORITY_HIERARCHY: List[str] = [
        "doctor_approved_consultation",
        "doctor_entered",
        "official_clinical_document",
        "lab_report",
        "prescription",
        "patient_reported",
        "ai_inference",
    ]

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
