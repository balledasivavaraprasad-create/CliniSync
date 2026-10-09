"""Worker abstraction for asynchronous document processing jobs.

Provides:
- DocumentTaskWorker protocol
- BackgroundDocumentWorker implementation with retry management and sanitized error recording
- Easy extensibility to Redis/Celery/RQ message queues
"""
from abc import ABC, abstractmethod
import asyncio
import re
from typing import Optional
import structlog

from app.db.database import get_db_context
from app.models.document import Document
from app.models.processing_job import ProcessingJob
from app.schemas.common import ProcessingStatus

logger = structlog.get_logger(__name__)


from app.utils.logging_sanitizer import sanitize_error_message


class DocumentTaskWorker(ABC):
    @abstractmethod
    async def process_document_async(
        self, document_id: str, is_reprocess: bool = False, max_retries: int = 2
    ) -> None:
        """Enqueue or run document processing asynchronously."""
        pass


import datetime

class BackgroundDocumentWorker(DocumentTaskWorker):
    """Default in-process background worker using FastAPI / asyncio background tasks."""

    async def process_document_async(
        self, document_id: str, is_reprocess: bool = False, max_retries: int = 2
    ) -> None:
        from app.services.pipeline_orchestrator import pipeline_orchestrator

        attempt = 0
        while attempt <= max_retries:
            attempt += 1
            try:
                logger.info(
                    "worker_processing_document_attempt",
                    document_id=document_id,
                    attempt=attempt,
                    is_reprocess=is_reprocess,
                )
                await pipeline_orchestrator.run(
                    document_id=document_id,
                    is_reprocess=is_reprocess,
                    attempt=attempt,
                    raise_on_error=True,
                )
                return
            except Exception as exc:
                clean_err = sanitize_error_message(exc)
                logger.error(
                    "worker_processing_attempt_failed",
                    document_id=document_id,
                    attempt=attempt,
                    error=clean_err,
                )

                if attempt <= max_retries:
                    # Update status to RETRY_PENDING before retrying
                    with get_db_context() as db:
                        doc = db.query(Document).filter(Document.id == document_id).first()
                        if doc:
                            doc.processing_status = ProcessingStatus.RETRY_PENDING.value
                            doc.processing_error_code = "TRANSIENT_PROCESSING_RETRY"

                        job = (
                            db.query(ProcessingJob)
                            .filter(
                                ProcessingJob.subject_id == document_id,
                                ProcessingJob.subject_type == "document",
                            )
                            .order_by(ProcessingJob.created_at.desc())
                            .first()
                        )
                        if job:
                            job.status = ProcessingStatus.RETRY_PENDING.value
                            job.stage = ProcessingStatus.RETRY_PENDING.value
                            job.attempts = attempt
                            job.last_error_code = "TRANSIENT_PROCESSING_RETRY"
                            job.last_error_detail = clean_err
                        db.commit()

                    await asyncio.sleep(0.2 * attempt)
                else:
                    # Terminal failure state recorded
                    with get_db_context() as db:
                        now = datetime.datetime.now(datetime.UTC)
                        doc = db.query(Document).filter(Document.id == document_id).first()
                        if doc:
                            doc.processing_status = ProcessingStatus.FAILED.value
                            doc.processing_error_code = "DOCUMENT_PROCESSING_FAILED"
                        job = (
                            db.query(ProcessingJob)
                            .filter(
                                ProcessingJob.subject_id == document_id,
                                ProcessingJob.subject_type == "document",
                            )
                            .order_by(ProcessingJob.created_at.desc())
                            .first()
                        )
                        if job:
                            job.status = ProcessingStatus.FAILED.value
                            job.stage = ProcessingStatus.FAILED.value
                            job.attempts = attempt
                            job.finished_at = now
                            job.last_error_code = "DOCUMENT_PROCESSING_FAILED"
                            job.last_error_detail = clean_err
                        db.commit()
                    return


task_worker = BackgroundDocumentWorker()
