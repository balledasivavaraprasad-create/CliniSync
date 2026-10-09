"""Comprehensive tests and static audit for application logging and PHI protection.

Verifies:
1. Structlog processor sanitization:
   - Passwords and credentials redacted
   - Authentication tokens (Bearer, JWT) redacted
   - API keys (Gemini, Groq) redacted
   - Sensitive identifiers (SSN, credit card numbers) redacted
   - Local filesystem paths redacted
   - Clinical documents, OCR text, voice transcripts, prompts masked
2. Opt-in development logging:
   - Disabled by default (ALLOW_DEBUG_PHI_LOGGING=False): outputs non-PHI length metadata
   - Explicit opt-in (ALLOW_DEBUG_PHI_LOGGING=True): outputs truncated preview with secrets scrubbed
3. Exception messages:
   - Sanitization ensures exceptions do not expose tokens, keys, or PHI
   - Unhandled 500 handler returns generic non-leaking message
4. Static audit:
   - Scans all backend python files to ensure no accidental logging of forbidden variables
"""

import glob
import re
import pytest
import structlog
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.utils.logging_sanitizer import (
    sanitize_text,
    sanitize_error_message,
    mask_clinical_content,
    phi_sanitizer_processor,
)

client = TestClient(app)


class TestLoggingSanitizer:
    def test_passwords_and_tokens_are_redacted(self):
        event = {
            "event": "user_login_attempt",
            "password": "SuperSecretPassword123!",
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozGzT",
            "access_token": "token_abc_123",
            "api_key": "gsk_testkey123456789012345678",
        }
        sanitized = phi_sanitizer_processor(None, "info", event)
        assert sanitized["password"] == "[REDACTED_SECRET]"
        assert sanitized["token"] == "[REDACTED_SECRET]"
        assert sanitized["access_token"] == "[REDACTED_SECRET]"
        assert sanitized["api_key"] == "[REDACTED_SECRET]"
        assert "SuperSecretPassword123!" not in str(sanitized)

    def test_bearer_tokens_and_jwts_scrubbed_from_text(self):
        sample_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozGzT"
        raw_msg = f"User authenticated with Bearer {sample_jwt} using key gsk_12345678901234567890"
        scrubbed = sanitize_text(raw_msg)
        assert "[REDACTED_TOKEN]" in scrubbed or "[REDACTED_JWT]" in scrubbed
        assert "[REDACTED_API_KEY]" in scrubbed
        assert sample_jwt not in scrubbed
        assert "gsk_12345678901234567890" not in scrubbed

    def test_sensitive_identifiers_scrubbed_from_text(self):
        raw_msg = "Patient SSN is 000-12-3456 and payment card 4111 2222 3333 4444"
        scrubbed = sanitize_text(raw_msg)
        assert "[REDACTED_SSN]" in scrubbed
        assert "[REDACTED_CARD]" in scrubbed
        assert "000-12-3456" not in scrubbed
        assert "4111 2222 3333 4444" not in scrubbed

    def test_filesystem_paths_scrubbed(self):
        raw_win = r"File saved at C:\Users\Doctor\SecretRecords\patient_chart.pdf"
        raw_unix = "/Users/doctor/SecretRecords/patient_chart.pdf"
        assert "[REDACTED_PATH]" in sanitize_text(raw_win)
        assert "[REDACTED_PATH]" in sanitize_text(raw_unix)
        assert "Doctor" not in sanitize_text(raw_win)

    def test_clinical_content_masked_by_default(self, monkeypatch):
        monkeypatch.setattr(settings, "ALLOW_DEBUG_PHI_LOGGING", False)
        event = {
            "event": "document_ocr_finished",
            "raw_text": "Patient has acute myocardial infarction and severe coronary artery disease.",
            "transcript": "Doctor: Start Metformin 500mg BID and Lisinopril 10mg daily.",
            "prompt": "Evaluate patient symptoms: chest pain radiating to left arm.",
        }
        sanitized = phi_sanitizer_processor(None, "info", event)
        assert "[REDACTED_RAW_TEXT]" in sanitized["raw_text"]
        assert "[REDACTED_TRANSCRIPT]" in sanitized["transcript"]
        assert "[REDACTED_PROMPT]" in sanitized["prompt"]
        assert "myocardial infarction" not in str(sanitized)
        assert "Metformin" not in str(sanitized)
        assert "chest pain" not in str(sanitized)

    def test_clinical_content_opt_in_debug_mode(self, monkeypatch):
        monkeypatch.setattr(settings, "ALLOW_DEBUG_PHI_LOGGING", True)
        event = {
            "event": "document_ocr_finished",
            "raw_text": "Patient has acute myocardial infarction and severe coronary artery disease.",
            "password": "never_log_this",
        }
        sanitized = phi_sanitizer_processor(None, "debug", event)
        assert "[DEBUG_RAW_TEXT_PREVIEW]" in sanitized["raw_text"]
        # Passwords remain strictly redacted even in debug mode
        assert sanitized["password"] == "[REDACTED_SECRET]"
        assert "never_log_this" not in str(sanitized)

    def test_exception_sanitization(self):
        exc = ValueError(
            "Failed processing C:\\Data\\patient_records.pdf with API key gsk_12345678901234567890 and token Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.abc"
        )
        clean = sanitize_error_message(exc)
        assert "[REDACTED_PATH]" in clean
        assert "[REDACTED_API_KEY]" in clean
        assert "[REDACTED_TOKEN]" in clean
        assert "C:\\Data" not in clean
        assert "gsk_12345678901234567890" not in clean


class TestHTTPExceptionPHILeakPrevention:
    def test_500_handler_does_not_leak_internal_exception_or_phi(self):
        # Request an invalid endpoint or cause unhandled error
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

        # Test uncaught_error_handler directly with a sensitive exception
        from app.api.errors import uncaught_error_handler
        from fastapi import Request

        scope = {"type": "http", "method": "GET", "path": "/test", "headers": []}
        req = Request(scope)
        sensitive_exc = RuntimeError("Database error on patient John Doe, SSN 123-45-6789, diagnosis cancer")
        import asyncio

        json_resp = asyncio.run(uncaught_error_handler(req, sensitive_exc))
        body = json_resp.body.decode("utf-8")
        assert "John Doe" not in body
        assert "123-45-6789" not in body
        assert "cancer" not in body
        assert "An unexpected server error occurred" in body


class TestStaticCodeAuditForSensitiveLogging:
    """Static AST/regex scanner over all backend python files to prevent regression."""

    def test_no_forbidden_direct_logging_in_backend(self):
        backend_files = glob.glob("backend/**/*.py", recursive=True)
        # Avoid false positives in the sanitizer utility itself
        checked_files = [f for f in backend_files if not f.endswith("logging_sanitizer.py")]

        # Patterns that should NEVER be logged directly as keyword arguments
        prohibited_kwarg_patterns = [
            re.compile(r'logger\.\w+\([^)]*password\s*='),
            re.compile(r'logger\.\w+\([^)]*hashed_password\s*='),
            re.compile(r'logger\.\w+\([^)]*raw_password\s*='),
            re.compile(r'logger\.\w+\([^)]*api_key\s*='),
            re.compile(r'logger\.\w+\([^)]*secret_key\s*='),
        ]

        violations = []
        for file_path in checked_files:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as fp:
                for lineno, line in enumerate(fp, 1):
                    for pat in prohibited_kwarg_patterns:
                        if pat.search(line):
                            violations.append(f"{file_path}:{lineno} -> {line.strip()}")

        assert not violations, f"Prohibited logging patterns detected:\n" + "\n".join(violations)
