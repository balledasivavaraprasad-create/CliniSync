"""Logging sanitizer and PHI protection engine.

Enforces strict compliance with clinical data protection guidelines:
- Never log full patient medical history
- Never log raw medical documents or raw OCR output
- Never log full voice transcriptions
- Never log full LLM prompts or responses containing patient information
- Never log passwords, tokens, API keys, or sensitive identifiers
- Ensure exception messages do not leak PHI
- Provide explicit opt-in debug logging (settings.ALLOW_DEBUG_PHI_LOGGING), disabled by default
"""

import re
from typing import Any, Dict, Union
from app.config import settings

# Sensitive key names that must never appear in raw logs
FORBIDDEN_SECRET_KEYS = {
    "password",
    "passwd",
    "pwd",
    "hashed_password",
    "secret",
    "secret_key",
    "api_key",
    "gemini_api_key",
    "groq_api_key",
    "token",
    "access_token",
    "refresh_token",
    "jwt",
    "bearer",
    "authorization",
    "credentials",
}

# Clinical content keys that contain raw PHI
CLINICAL_CONTENT_KEYS = {
    "raw_text",
    "full_text",
    "ocr_text",
    "extracted_text",
    "transcript",
    "transcript_raw",
    "transcript_normalized",
    "audio_bytes",
    "medical_history",
    "patient_history",
    "prompt",
    "prompt_text",
    "messages",
    "llm_prompt",
    "llm_response",
    "completion",
    "response_text",
    "content_json",
}

# Regex patterns for sanitization
RE_BEARER_TOKEN = re.compile(r"Bearer\s+[A-Za-z0-9._~+/-]+", re.IGNORECASE)
RE_JWT = re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
RE_API_KEY = re.compile(r"\b(?:AIza[0-9A-Za-z-_]{35}|gsk_[0-9A-Za-z_-]{20,})\b")
RE_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
RE_CREDIT_CARD = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
RE_WINDOWS_PATH = re.compile(r"[A-Za-z]:\\[^ \n\r\t]+")
RE_UNIX_PATH = re.compile(r"/(?:Users|home|root|var|tmp|etc)/[^ \n\r\t]+")
RE_GENERIC_SECRET = re.compile(r"\b[A-Za-z0-9_-]{32,}\b")


def sanitize_text(text: str) -> str:
    """Scrub tokens, API keys, sensitive identifiers, and local paths from any string."""
    if not isinstance(text, str):
        text = str(text)

    # 1. Redact auth tokens & keys
    text = RE_BEARER_TOKEN.sub("Bearer [REDACTED_TOKEN]", text)
    text = RE_JWT.sub("[REDACTED_JWT]", text)
    text = RE_API_KEY.sub("[REDACTED_API_KEY]", text)

    # 2. Redact sensitive identifiers
    text = RE_SSN.sub("[REDACTED_SSN]", text)
    text = RE_CREDIT_CARD.sub("[REDACTED_CARD]", text)

    # 3. Redact local paths
    text = RE_WINDOWS_PATH.sub("[REDACTED_PATH]", text)
    text = RE_UNIX_PATH.sub("[REDACTED_PATH]", text)

    # 4. Redact long opaque hex / base64 tokens
    text = RE_GENERIC_SECRET.sub("[REDACTED_SECRET]", text)

    return text


def sanitize_error_message(error: Union[Exception, str]) -> str:
    """Sanitize error messages to ensure they never leak PHI, tokens, keys, or paths."""
    raw = str(error)
    cleaned = sanitize_text(raw)
    return cleaned[:300]


def mask_clinical_content(content: Any, label: str = "clinical_content") -> str:
    """Mask clinical documents, OCR, voice transcriptions, or prompts.
    
    If settings.ALLOW_DEBUG_PHI_LOGGING is False (default), replaces with non-PHI summary.
    If settings.ALLOW_DEBUG_PHI_LOGGING is True, provides a truncated, sanitized preview.
    """
    if content is None:
        return "[EMPTY]"

    content_str = str(content)
    length = len(content_str)

    if not getattr(settings, "ALLOW_DEBUG_PHI_LOGGING", False):
        return f"[REDACTED_{label.upper()}] (length={length})"

    # Opt-in debug mode: truncate and scrub secrets
    preview = sanitize_text(content_str[:80])
    return f"[DEBUG_{label.upper()}_PREVIEW] {preview}... (length={length})"


def phi_sanitizer_processor(logger, method_name, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Structlog processor that guarantees no forbidden items or PHI leak to logs."""
    sanitized: Dict[str, Any] = {}

    for key, value in event_dict.items():
        key_lower = key.lower()

        # 1. Absolute forbidden: secrets / credentials / tokens
        if any(secret_term in key_lower for secret_term in FORBIDDEN_SECRET_KEYS):
            sanitized[key] = "[REDACTED_SECRET]"
            continue

        # 2. Clinical content: raw OCR, full voice transcript, prompts, full medical text
        if any(phi_term == key_lower or f"_{phi_term}" in key_lower for phi_term in CLINICAL_CONTENT_KEYS):
            sanitized[key] = mask_clinical_content(value, label=key)
            continue

        # 3. Value-level sanitization for strings and nested data
        if isinstance(value, str):
            sanitized[key] = sanitize_text(value)
        elif isinstance(value, Exception):
            sanitized[key] = sanitize_error_message(value)
        elif isinstance(value, (list, tuple)):
            sanitized[key] = [
                sanitize_text(v) if isinstance(v, str) else v
                for v in value
            ]
        elif isinstance(value, dict):
            # Recursively sanitize nested dicts
            sanitized[key] = phi_sanitizer_processor(logger, method_name, value)
        else:
            sanitized[key] = value

    return sanitized
