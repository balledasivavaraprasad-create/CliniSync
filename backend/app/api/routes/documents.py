import os
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_current_user, get_request_id, CurrentUser
from app.schemas.document import DocumentResponse, DocumentPageResponse, DocumentStatusResponse
from app.services.document_service import DocumentService
from app.models.document import Document
from app.models.processing_job import ProcessingJob
from app.api.errors import NotFoundError

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
    from app.api.deps import require_patient_id
    pid = require_patient_id(db, patient_id)
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
    from app.api.deps import require_patient_id
    pid = require_patient_id(db, patient_id or "pat_demo_patient_001")
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
    request_id: str = Depends(get_request_id),
):
    from app.api.deps import require_patient_id
    pid = require_patient_id(db, patient_id)
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
    request_id: str = Depends(get_request_id),
):
    from app.api.deps import require_patient_id
    if patient_id:
        pid = require_patient_id(db, patient_id)
        docs = DocumentService.list_by_patient(db, pid)
    else:
        docs = db.query(Document).order_by(Document.created_at.desc()).limit(100).all()
    return {
        "success": True,
        "data": [DocumentResponse.model_validate(d).model_dump() for d in docs],
        "meta": {"request_id": request_id, "source": "db"},
    }



@router.get("/documents/{document_id}")
def get_document(
    document_id: str,
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    doc = DocumentService.get(db, document_id)
    return {
        "success": True,
        "data": DocumentResponse.model_validate(doc).model_dump(),
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.get("/documents/{document_id}/file")
def stream_document_file(
    document_id: str,
    db: Session = Depends(get_db_session),
):
    doc = DocumentService.get(db, document_id)
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
    request_id: str = Depends(get_request_id),
):
    page = DocumentService.get_page(db, document_id, n)
    return {
        "success": True,
        "data": DocumentPageResponse.model_validate(page).model_dump(),
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.get("/documents/{document_id}/status")
def get_document_status(
    document_id: str,
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    doc = DocumentService.get(db, document_id)
    all_stages = [
        {"name": "uploaded", "label": "Uploaded", "completed": True},
        {"name": "extracting_text", "label": "Extracting Text", "completed": doc.processing_status not in ["uploaded"]},
        {"name": "classifying", "label": "Classifying", "completed": doc.processing_status in ["classifying", "extracting_entities", "normalizing", "validating", "complete"]},
        {"name": "extracting_entities", "label": "Extracting Clinical Information", "completed": doc.processing_status in ["extracting_entities", "normalizing", "validating", "complete"]},
        {"name": "normalizing", "label": "Normalizing & Linking Evidence", "completed": doc.processing_status in ["normalizing", "validating", "complete"]},
        {"name": "complete", "label": "Complete", "completed": doc.processing_status == "complete"},
    ]

    return {
        "success": True,
        "data": {
            "document_id": doc.id,
            "status": doc.processing_status,
            "current_stage": doc.processing_status,
            "stages": all_stages,
            "error_code": doc.processing_error_code,
        },
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.post("/documents/{document_id}/process")
async def process_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    from app.services.pipeline_orchestrator import pipeline_orchestrator
    doc = DocumentService.get(db, document_id)
    background_tasks.add_task(pipeline_orchestrator.run, document_id=document_id, is_reprocess=False)
    return {
        "success": True,
        "data": {
            "document_id": doc.id,
            "status": "extracting_text",
            "message": "Processing pipeline initiated",
        },
        "meta": {"request_id": request_id, "source": "db"},
    }


@router.post("/documents/{document_id}/reprocess")
async def reprocess_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    from app.services.pipeline_orchestrator import pipeline_orchestrator
    doc = DocumentService.get(db, document_id)
    background_tasks.add_task(pipeline_orchestrator.run, document_id=document_id, is_reprocess=True)
    return {
        "success": True,
        "data": {
            "document_id": doc.id,
            "status": "extracting_text",
            "message": "Reprocessing pipeline initiated",
        },
        "meta": {"request_id": request_id, "source": "db"},
    }
