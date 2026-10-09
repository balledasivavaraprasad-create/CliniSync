import os
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import (
    get_db_session,
    get_current_user,
    get_request_id,
    CurrentUser,
    require_patient_access,
    require_document_access,
    get_accessible_patient_ids,
)
from app.schemas.document import DocumentResponse, DocumentPageResponse, DocumentStatusResponse
from app.services.document_service import DocumentService
from app.models.document import Document
from app.models.processing_job import ProcessingJob
from app.api.errors import NotFoundError, ForbiddenError

router = APIRouter(tags=["documents"])


@router.post("/patients/{patient_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    patient_id: str,
    file: UploadFile = File(...),
    uploaded_via: str = Form("upload"),
    document_type_hint: Optional[str] = Form(None),
    document_date: Optional[str] = Form(None),
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    pid = require_patient_access(patient_id, db, user)
    content = await file.read()
    doc, is_duplicate = DocumentService.store_document(
        db=db,
        patient_id=pid,
        filename=file.filename or "uploaded_file",
        content=content,
        declared_mime=file.content_type or "application/octet-stream",
        uploaded_via=uploaded_via,
        document_type_hint=document_type_hint,
        document_date=document_date,
        actor=user.id,
        request_id=request_id,
    )
    resp = DocumentResponse.model_validate(doc)
    resp.duplicate = is_duplicate
    return {
        "success": True,
        "data": resp.model_dump(),
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.post("/documents/upload", status_code=status.HTTP_201_CREATED)
async def upload_document_legacy(
    file: UploadFile = File(...),
    patient_id: Optional[str] = Form("pat_demo_patient_001"),
    uploaded_via: str = Form("upload"),
    document_type_hint: Optional[str] = Form(None),
    document_date: Optional[str] = Form(None),
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    pid = require_patient_access(patient_id or "pat_demo_patient_001", db, user)
    content = await file.read()
    doc, is_duplicate = DocumentService.store_document(
        db=db,
        patient_id=pid,
        filename=file.filename or "uploaded_file",
        content=content,
        declared_mime=file.content_type or "application/octet-stream",
        uploaded_via=uploaded_via,
        document_type_hint=document_type_hint,
        document_date=document_date,
        actor=user.id,
        request_id=request_id,
    )
    resp = DocumentResponse.model_validate(doc)
    resp.duplicate = is_duplicate
    return {
        "success": True,
        "data": resp.model_dump(),
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.get("/patients/{patient_id}/documents")
def list_patient_documents(
    patient_id: str,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    pid = require_patient_access(patient_id, db, user)
    docs = DocumentService.list_by_patient(db, pid)
    return {
        "success": True,
        "data": [DocumentResponse.model_validate(d).model_dump() for d in docs],
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.get("/documents")
def list_documents_query(
    patient_id: Optional[str] = None,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    if patient_id:
        pid = require_patient_access(patient_id, db, user)
        docs = DocumentService.list_by_patient(db, pid)
    else:
        # If no patient specified, filter documents to only those accessible to this user
        accessible_pids = get_accessible_patient_ids(db, user)
        q = db.query(Document)
        if accessible_pids is not None:
            q = q.filter(Document.patient_id.in_(accessible_pids))
        docs = q.order_by(Document.created_at.desc()).limit(100).all()

    return {
        "success": True,
        "data": [DocumentResponse.model_validate(d).model_dump() for d in docs],
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.get("/documents/stale")
def list_stale_documents(
    max_age_seconds: int = 300,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    """Identifies active in-flight processing jobs that have not progressed within max_age_seconds."""
    if not (user.is_clinical or user.is_admin):
        raise ForbiddenError("Only clinical or admin users can inspect stale processing jobs.")
    stale_jobs = DocumentService.find_stale_jobs(db, max_age_seconds=max_age_seconds)
    return {
        "success": True,
        "data": stale_jobs,
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.post("/documents/recover-stale")
def recover_stale_documents(
    background_tasks: BackgroundTasks,
    max_age_seconds: int = 300,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    """Batch recovery mechanism that identifies and safely re-queues stale document processing jobs."""
    if not (user.is_clinical or user.is_admin):
        raise ForbiddenError("Only clinical or admin users can initiate stale job recovery.")
    recovered_ids = DocumentService.recover_stale_jobs(
        db, max_age_seconds=max_age_seconds, background_tasks=background_tasks
    )
    return {
        "success": True,
        "data": {
            "recovered_count": len(recovered_ids),
            "recovered_document_ids": recovered_ids,
        },
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.get("/documents/{document_id}")
def get_document(
    document_id: str,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    doc = require_document_access(document_id, db, user)
    return {
        "success": True,
        "data": DocumentResponse.model_validate(doc).model_dump(),
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.get("/documents/{document_id}/file")
def stream_document_file(
    document_id: str,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
):
    doc = require_document_access(document_id, db, user)
    file_path = Path(doc.stored_path)
    if not file_path.exists():
        raise NotFoundError("Stored document file does not exist on disk")

    return FileResponse(
        path=str(file_path),
        media_type=doc.mime_type,
        filename=doc.original_filename,
    )


@router.get("/documents/{document_id}/pages/{n}")
def get_document_page(
    document_id: str,
    n: int,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    doc = require_document_access(document_id, db, user)
    page = DocumentService.get_page(db, doc.id, n)
    return {
        "success": True,
        "data": DocumentPageResponse.model_validate(page).model_dump(),
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.get("/documents/{document_id}/status")
def get_document_status(
    document_id: str,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    doc = require_document_access(document_id, db, user)
    job = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.subject_id == document_id, ProcessingJob.subject_type == "document")
        .order_by(ProcessingJob.created_at.desc())
        .first()
    )

    all_stages = [
        {"name": "UPLOADED", "label": "Uploaded", "completed": True},
        {"name": "QUEUED", "label": "Queued", "completed": doc.processing_status not in ["UPLOADED", "uploaded"]},
        {"name": "PROCESSING", "label": "Processing", "completed": doc.processing_status not in ["UPLOADED", "uploaded", "QUEUED", "queued"]},
        {"name": "EXTRACTING", "label": "Extracting Clinical Information", "completed": doc.processing_status in ["EXTRACTING", "VALIDATING", "COMPLETED", "extracting", "validating", "complete"]},
        {"name": "VALIDATING", "label": "Validating & Linking Evidence", "completed": doc.processing_status in ["VALIDATING", "COMPLETED", "validating", "complete"]},
        {"name": "COMPLETED", "label": "Completed", "completed": doc.processing_status in ["COMPLETED", "complete"]},
    ]

    return {
        "success": True,
        "data": {
            "document_id": doc.id,
            "status": str(doc.processing_status),
            "current_stage": str(job.stage if job else doc.processing_status),
            "started_at": job.started_at.isoformat() if (job and job.started_at) else None,
            "finished_at": job.finished_at.isoformat() if (job and job.finished_at) else None,
            "completion_time": job.finished_at.isoformat() if (job and job.finished_at) else None,
            "retry_count": job.attempts if job else 0,
            "error_code": doc.processing_error_code or (job.last_error_code if job else None),
            "error_detail": job.last_error_detail if job else None,
            "failure_reason": job.last_error_detail if job else None,
            "stages": all_stages,
        },
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.post("/documents/{document_id}/process")
async def process_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    from app.services.task_worker import task_worker
    from app.schemas.common import ProcessingStatus
    doc = require_document_access(document_id, db, user)

    doc.processing_status = ProcessingStatus.QUEUED.value
    doc.processing_error_code = None

    job = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.subject_id == document_id, ProcessingJob.subject_type == "document")
        .order_by(ProcessingJob.created_at.desc())
        .first()
    )
    if not job or job.status in ("COMPLETED", "FAILED"):
        from app.utils.ids import job_id as generate_job_id
        job = ProcessingJob(
            id=generate_job_id(),
            subject_type="document",
            subject_id=doc.id,
            stage=ProcessingStatus.QUEUED.value,
            status=ProcessingStatus.QUEUED.value,
            attempts=0,
        )
        db.add(job)
    else:
        job.stage = ProcessingStatus.QUEUED.value
        job.status = ProcessingStatus.QUEUED.value
    db.commit()

    background_tasks.add_task(task_worker.process_document_async, document_id=doc.id, is_reprocess=False)
    return {
        "success": True,
        "data": {
            "document_id": doc.id,
            "status": "QUEUED",
            "message": "Processing pipeline initiated",
        },
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.post("/documents/{document_id}/reprocess")
async def reprocess_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    doc = require_document_access(document_id, db, user)

    from app.services.audit_service import write_audit
    write_audit(
        db=db,
        actor=user.id,
        action="document.reprocess_requested",
        entity_type="document",
        entity_id=doc.id,
        patient_id=doc.patient_id,
        after={"reprocess": True},
        request_id=request_id,
    )

    from app.schemas.common import ProcessingStatus
    doc.processing_status = ProcessingStatus.QUEUED.value
    doc.processing_error_code = None

    job = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.subject_id == document_id, ProcessingJob.subject_type == "document")
        .order_by(ProcessingJob.created_at.desc())
        .first()
    )
    if not job or job.status in ("COMPLETED", "FAILED"):
        from app.utils.ids import job_id as generate_job_id
        job = ProcessingJob(
            id=generate_job_id(),
            subject_type="document",
            subject_id=doc.id,
            stage=ProcessingStatus.QUEUED.value,
            status=ProcessingStatus.QUEUED.value,
            attempts=0,
        )
        db.add(job)
    else:
        job.stage = ProcessingStatus.QUEUED.value
        job.status = ProcessingStatus.QUEUED.value
    db.commit()

    from app.services.task_worker import task_worker
    background_tasks.add_task(task_worker.process_document_async, document_id=doc.id, is_reprocess=True)
    return {
        "success": True,
        "data": {
            "document_id": doc.id,
            "status": "QUEUED",
            "message": "Reprocessing pipeline initiated",
        },
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.post("/documents/{document_id}/recover")
async def recover_single_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    """Safely recovers and re-runs a failed or stale document processing job."""
    doc = require_document_access(document_id, db, user)
    DocumentService.recover_document(
        db=db,
        document_id=doc.id,
        background_tasks=background_tasks,
        actor=user.id,
    )
    return {
        "success": True,
        "data": {
            "document_id": doc.id,
            "status": "QUEUED",
            "message": "Document recovery initiated",
        },
        "meta": {"request_id": request_id, "source": "db"},
    }
