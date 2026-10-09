import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel, Field

from app.ai.gateway import LLMGateway
from app.api.errors import (
    LLMError,
    LLMUnavailableError,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMAuthenticationError,
    LLMOutputParsingError,
)
from app.db.database import get_db_context
from app.models.audit_log import LLMCallLog
from app.models.clinical_fact import ClinicalFact
from app.models.clinical_memory import ClinicalMemory
from app.schemas.common import VerificationStatus


class SampleOutputSchema(BaseModel):
    summary: str
    score: float = Field(ge=0.0, le=1.0)


@pytest.fixture
def gateway():
    return LLMGateway.get_instance()


@pytest.mark.asyncio
async def test_llm_gateway_async_execution_non_blocking(gateway):
    """
    Verifies that complete_text_async and complete_json_async are true async operations
    and do not block the asyncio event loop while waiting for LLM responses.
    """
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="Async test reply"))]
    mock_resp.get.return_value = "mock_model"

    async def mock_acompletion(*args, **kwargs):
        # Yield control back to event loop to simulate network latency
        await asyncio.sleep(0.05)
        return mock_resp

    with patch.object(gateway.router, "acompletion", side_effect=mock_acompletion):
        # Run two LLM calls concurrently with an async background timer
        loop_tick = 0

        async def ticker():
            nonlocal loop_tick
            for _ in range(3):
                await asyncio.sleep(0.01)
                loop_tick += 1

        tick_task = asyncio.create_task(ticker())
        call1 = gateway.complete_text_async("async_test", [{"role": "user", "content": "hi"}])
        call2 = gateway.complete_text_async("async_test", [{"role": "user", "content": "hi2"}])

        res1, res2, _ = await asyncio.gather(call1, call2, tick_task)

        assert res1 == "Async test reply"
        assert res2 == "Async test reply"
        # The ticker task must have been able to run concurrently
        assert loop_tick >= 1


@pytest.mark.asyncio
async def test_llm_gateway_explicit_timeout_enforced(gateway):
    """
    Verifies explicit timeouts are passed and enforced on calls, raising LLMTimeoutError on timeout.
    """
    async def mock_slow_acompletion(*args, **kwargs):
        await asyncio.sleep(1.0)
        return MagicMock()

    with patch.object(gateway.router, "acompletion", side_effect=mock_slow_acompletion):
        with pytest.raises(LLMTimeoutError) as exc_info:
            await gateway.complete_text_async(
                task="test_timeout",
                messages=[{"role": "user", "content": "timeout test"}],
                timeout=0.05,
            )

        assert exc_info.value.code == "LLM_TIMEOUT"
        assert "timed out after 0.1s" in exc_info.value.message or "timed out" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_llm_gateway_bounded_retries(gateway):
    """
    Verifies retries are bounded and never retry indefinitely.
    """
    call_count = 0

    async def mock_failing_acompletion(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        # LiteLLM router num_retries argument is bounded
        assert kwargs.get("num_retries", 0) <= 2
        raise ConnectionError("Upstream connection reset")

    with patch.object(gateway.router, "acompletion", side_effect=mock_failing_acompletion):
        with pytest.raises(LLMUnavailableError) as exc_info:
            await gateway.complete_text_async(
                task="test_retries",
                messages=[{"role": "user", "content": "retry test"}],
                max_retries=1,
            )

        assert exc_info.value.code == "LLM_UNAVAILABLE"


@pytest.mark.asyncio
async def test_llm_gateway_provider_error_normalization(gateway):
    """
    Verifies provider-specific errors normalize to structured domain errors.
    """
    # 1. 429 Rate Limit
    async def mock_rate_limit(*args, **kwargs):
        raise RuntimeError("HTTP 429 Too Many Requests: Rate limit exceeded or quota exhausted")

    with patch.object(gateway.router, "acompletion", side_effect=mock_rate_limit):
        with pytest.raises(LLMRateLimitError) as exc_info:
            await gateway.complete_text_async("task_rate", [{"role": "user", "content": "test"}])
        assert exc_info.value.code == "LLM_RATE_LIMIT"

    # 2. Authentication failure / Missing API key
    async def mock_auth_error(*args, **kwargs):
        raise ValueError("Missing Gemini API key. Set the GEMINI_API_KEY environment variable.")

    with patch.object(gateway.router, "acompletion", side_effect=mock_auth_error):
        with pytest.raises(LLMAuthenticationError) as exc_info:
            await gateway.complete_text_async("task_auth", [{"role": "user", "content": "test"}])
        assert exc_info.value.code == "LLM_AUTH_ERROR"


@pytest.mark.asyncio
async def test_llm_gateway_malformed_output_rejected_safely(gateway):
    """
    Verifies malformed JSON or schema violation is rejected safely via LLMOutputParsingError.
    """
    bad_resp = MagicMock()
    bad_resp.choices = [MagicMock(message=MagicMock(content="Here is some non-json text that cannot be parsed."))]
    bad_resp.get.return_value = "mock_model"

    async def mock_bad_json(*args, **kwargs):
        return bad_resp

    with patch.object(gateway.router, "acompletion", side_effect=mock_bad_json):
        with pytest.raises(LLMOutputParsingError) as exc_info:
            await gateway.complete_json_async(
                task="test_malformed_json",
                messages=[{"role": "user", "content": "generate json"}],
                schema=SampleOutputSchema,
                slot="llm_extract",
            )
        assert exc_info.value.code == "LLM_MALFORMED_OUTPUT"


@pytest.mark.asyncio
async def test_llm_gateway_metadata_recorded_every_call(gateway):
    """
    Verifies every LLM call logs:
    - request ID
    - model/provider identifier
    - operation name (task)
    - latency
    - success/failure status
    """
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content=json.dumps({"summary": "Good report", "score": 0.95})))]
    mock_resp.get.return_value = "provider_groq_llama3"

    custom_request_id = "req_custom_tracking_12345"

    with patch.object(gateway.router, "acompletion", return_value=mock_resp):
        res = await gateway.complete_json_async(
            task="clinical_extraction_audit",
            messages=[{"role": "user", "content": "extract"}],
            schema=SampleOutputSchema,
            request_id=custom_request_id,
        )
        assert res.summary == "Good report"
        assert res.score == 0.95

    # Check LLMCallLog
    with get_db_context() as db:
        log = (
            db.query(LLMCallLog)
            .filter(LLMCallLog.request_id == custom_request_id)
            .first()
        )
        assert log is not None
        assert log.task == "clinical_extraction_audit"
        assert log.logical_slot == "llm_extract"
        assert log.provider_model_used == "provider_groq_llama3"
        assert log.latency_ms >= 0.0
        assert log.success is True
        assert log.created_at is not None


@pytest.mark.asyncio
async def test_pipeline_clean_separation_llm_evidence_persistence():
    """
    Verifies the pipeline cleanly separates:
    LLM call -> Parse output -> Validate schema -> Evidence validation -> Database write.
    Raw LLM output NEVER directly becomes approved clinical memory.
    """
    from app.services.extraction_service import extraction_service
    from app.schemas.ai_contracts import ExtractionResult, ExtractionDiagnosis, EvidenceReference

    # 1. Mock valid LLM response
    mock_diag = ExtractionDiagnosis(
        text="Hypertension",
        date="2026-06-01",
        confidence=0.92,
        evidence=EvidenceReference(text="Patient has Essential Hypertension diagnosed on 2026-06-01", page=1)
    )
    mock_extraction = ExtractionResult(diagnoses=[mock_diag])

    # ExtractionService produces in-memory structured Pydantic object
    with patch("app.ai.gateway.llm_gateway.complete_json_async", return_value=mock_extraction):
        pages = [{"page_number": 1, "text": "Patient has Essential Hypertension diagnosed on 2026-06-01"}]
        result = await extraction_service.extract(pages=pages, doc_type="consultation_note")

        assert isinstance(result, ExtractionResult)
        assert len(result.diagnoses) == 1
        assert result.diagnoses[0].text == "Hypertension"

    # Verify that NO raw clinical memory was created by extraction alone
    with get_db_context() as db:
        mems = db.query(ClinicalMemory).filter(ClinicalMemory.content_json.like("%Hypertension%")).all()
        assert len(mems) == 0
