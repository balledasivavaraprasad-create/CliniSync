import threading
import time
from typing import Any, Dict, List, Optional
import structlog

logger = structlog.get_logger(__name__)


class MetricsService:
    """
    Centralized in-memory metrics tracker for AI operations, document pipeline, and validation gates.
    Tracks counts, failures, retries, fallback usage, latencies, and validation blocks.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reset_internal()

    def _reset_internal(self) -> None:
        self._model_calls = 0
        self._model_successes = 0
        self._model_failures = 0
        self._retries = 0
        self._fallback_usage = 0
        self._extraction_failures = 0
        self._validation_failures = 0
        self._gate1_failures = 0
        self._gate2_failures = 0
        self._latencies: List[float] = []
        self._task_counts: Dict[str, int] = {}
        self._model_counts: Dict[str, int] = {}
        self._stage_durations: Dict[str, List[float]] = {}

    def reset(self) -> None:
        with self._lock:
            self._reset_internal()

    def record_model_call(
        self,
        task: str,
        slot: str,
        model: str,
        latency_ms: float,
        success: bool,
        fallback_depth: int = 0,
        retries: int = 0,
        error: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        with self._lock:
            self._model_calls += 1
            if success:
                self._model_successes += 1
            else:
                self._model_failures += 1

            self._retries += retries
            if fallback_depth > 0:
                self._fallback_usage += 1

            self._latencies.append(latency_ms)
            # Keep latencies array bounded to last 1000 items
            if len(self._latencies) > 1000:
                self._latencies.pop(0)

            self._task_counts[task] = self._task_counts.get(task, 0) + 1
            self._model_counts[model] = self._model_counts.get(model, 0) + 1

        logger.info(
            "ai_model_call",
            task=task,
            slot=slot,
            model=model,
            latency_ms=round(latency_ms, 2),
            success=success,
            retries=retries,
            fallback_depth=fallback_depth,
            error=error,
            request_id=request_id,
        )

    def record_extraction_failure(self, document_id: str, reason: str) -> None:
        with self._lock:
            self._extraction_failures += 1

        logger.warning(
            "ai_extraction_failure",
            document_id=document_id,
            reason=reason,
        )

    def record_gate1_failure(self, consultation_id: str, reason: str, patient_id: Optional[str] = None) -> None:
        with self._lock:
            self._validation_failures += 1
            self._gate1_failures += 1

        logger.warning(
            "gate1_validation_failure",
            consultation_id=consultation_id,
            patient_id=patient_id,
            reason=reason,
        )

    def record_gate2_failure(self, patient_id: str, reason: str) -> None:
        with self._lock:
            self._validation_failures += 1
            self._gate2_failures += 1

        logger.warning(
            "gate2_validation_failure",
            patient_id=patient_id,
            reason=reason,
        )

    def record_stage_duration(self, stage: str, duration_ms: float) -> None:
        with self._lock:
            if stage not in self._stage_durations:
                self._stage_durations[stage] = []
            self._stage_durations[stage].append(duration_ms)
            if len(self._stage_durations[stage]) > 500:
                self._stage_durations[stage].pop(0)

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            avg_latency = (
                round(sum(self._latencies) / len(self._latencies), 2)
                if self._latencies
                else 0.0
            )
            max_latency = round(max(self._latencies), 2) if self._latencies else 0.0
            min_latency = round(min(self._latencies), 2) if self._latencies else 0.0

            stage_avg = {}
            for stg, durs in self._stage_durations.items():
                if durs:
                    stage_avg[stg] = round(sum(durs) / len(durs), 2)

            return {
                "ai_metrics": {
                    "model_calls": self._model_calls,
                    "successes": self._model_successes,
                    "failures": self._model_failures,
                    "retries": self._retries,
                    "fallback_usage": self._fallback_usage,
                    "extraction_failures": self._extraction_failures,
                    "validation_failures": self._validation_failures,
                    "gate1_failures": self._gate1_failures,
                    "gate2_failures": self._gate2_failures,
                    "latency_ms": {
                        "average": avg_latency,
                        "min": min_latency,
                        "max": max_latency,
                    },
                    "calls_by_task": dict(self._task_counts),
                    "calls_by_model": dict(self._model_counts),
                },
                "pipeline_stage_avg_duration_ms": stage_avg,
            }


metrics_service = MetricsService()
