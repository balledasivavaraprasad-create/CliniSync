import os
import re
from pathlib import Path
from typing import Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.config import settings
from app.models.document import Document, DocumentPage
from app.models.patient import Patient
from app.models.processing_job import ProcessingJob
from app.models.contradiction import Contradiction
from app.utils.hashing import compute_sha256
from app.utils.ids import document_id as generate_doc_id, job_id as generate_job_id, contradiction_id
from app.api.errors import (
    NotFoundError,
    FileTooLargeError,
    UnsupportedFileTypeError,
    BadRequestError,
)
from app.services.audit_service import write_audit


ALLOWED_EXTENSIONS_MAP = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
}

DISALLOWED_EXTENSIONS = {
    ".exe", ".sh", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".mjs",
    ".py", ".rb", ".php", ".phtml", ".html", ".htm", ".svg", ".dll",
    ".so", ".dylib", ".bin", ".iso", ".zip", ".tar", ".gz"
}


def sanitize_display_filename(filename: str) -> str:
    """Sanitize user-provided filename for safe database/display record keeping only."""
    clean = os.path.basename(filename)
    clean = re.sub(r"[^\w\.-]", "_", clean)
    return clean or "document.bin"


def detect_magic_mime_type(content: bytes) -> Optional[str]:
    """Inspect magic bytes to determine actual file format."""
    if len(content) < 4:
        return None
    if content.startswith(b"%PDF"):
        return "application/pdf"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if content.startswith(b"ID3") or content.startswith(b"\xff\xfb") or content.startswith(b"\xff\xf3") or content.startswith(b"\xff\xf2"):
        return "audio/mpeg"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WAVE":
        return "audio/wav"
    return None


def validate_and_inspect_file(
    content: bytes, filename: str, declared_mime: str
) -> Tuple[str, str]:
    """
    Validates file extension, magic bytes, MIME integrity, and structural validity.
    Returns: (detected_mime, safe_ext)
    Raises: BadRequestError, FileTooLargeError, UnsupportedFileTypeError
    """
    # 1. Non-empty check
    if not content or len(content) == 0:
        raise BadRequestError("Uploaded file is empty (0 bytes).")

    # 2. Size limit
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise FileTooLargeError(
            f"File size {len(content)} bytes exceeds the maximum limit of {settings.MAX_UPLOAD_MB} MB."
        )

    # 3. Extension validation
    ext = Path(filename).suffix.lower()
    if not ext or ext in DISALLOWED_EXTENSIONS or ext not in ALLOWED_EXTENSIONS_MAP:
        raise UnsupportedFileTypeError(
            f"File extension '{ext}' is not permitted. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS_MAP.keys()))}"
        )

    # 4. Magic byte inspection
    detected_mime = detect_magic_mime_type(content)
    if not detected_mime:
        raise UnsupportedFileTypeError(
            "File content signature does not match any allowed document or image format."
        )

    # Verify detected MIME is in configured allowed list
    if detected_mime not in settings.allowed_mime_list:
        raise UnsupportedFileTypeError(f"MIME type '{detected_mime}' is not permitted.")

    # 5. Extension vs detected MIME consistency (anti-spoofing)
    expected_mime = ALLOWED_EXTENSIONS_MAP[ext]
    if expected_mime != detected_mime:
        raise UnsupportedFileTypeError(
            f"File extension '{ext}' does not match content signature '{detected_mime}'."
        )

    # 6. Declared MIME vs detected MIME consistency
    if declared_mime and declared_mime != "application/octet-stream":
        # Allow jpg/jpeg interchangeably
        if declared_mime != detected_mime:
            # Check if both are JPEG aliases
            if not (declared_mime == "image/jpeg" and detected_mime == "image/jpeg"):
                raise UnsupportedFileTypeError(
                    f"Declared MIME '{declared_mime}' does not match detected file content '{detected_mime}'."
                )

    # 7. Structural integrity and corruption verification
    if detected_mime == "application/pdf":
        try:
            import fitz
            pdf = fitz.open(stream=content, filetype="pdf")
            if pdf.is_encrypted:
                pdf.close()
                raise UnsupportedFileTypeError("Encrypted/password-protected PDF files are not supported.")
            if pdf.page_count < 1:
                pdf.close()
                raise UnsupportedFileTypeError("PDF file contains no readable pages.")
            # Verify stream integrity of first page
            _ = pdf[0].get_text()
            pdf.close()
        except fitz.FileDataError as exc:
            raise UnsupportedFileTypeError(f"Uploaded PDF file is corrupted or unreadable: {exc}")
        except Exception as exc:
            if isinstance(exc, UnsupportedFileTypeError):
                raise
            raise UnsupportedFileTypeError(f"Uploaded PDF file is corrupted or unreadable: {exc}")

    elif detected_mime.startswith("image/"):
        try:
            import io
            from PIL import Image
            img = Image.open(io.BytesIO(content))
            img.verify()
        except Exception as exc:
            raise UnsupportedFileTypeError(f"Uploaded image is corrupted or invalid: {exc}")

    return detected_mime, ext


def preprocess_camera_image(content: bytes) -> bytes:
    """Preprocess camera uploads: EXIF auto-orient, max dimension downscale, autocontrast normalize."""
    import io
    from PIL import Image, ImageOps

    try:
        img = Image.open(io.BytesIO(content))
        img = ImageOps.exif_transpose(img)

        max_dim = 2048
        if img.width > max_dim or img.height > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        if img.mode in ("RGB", "L"):
            img = ImageOps.autocontrast(img, cutoff=0.5)

        out_io = io.BytesIO()
        fmt = img.format if img.format in ("JPEG", "PNG", "WEBP") else "JPEG"
        if fmt == "JPEG" and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(out_io, format=fmt, quality=90)
        return out_io.getvalue()
    except Exception:
        return content


class DocumentService:
    @staticmethod
    def store_document(
        db: Session,
        patient_id: str,
        filename: str,
        content: bytes,
        declared_mime: str,
        uploaded_via: str = "upload",
        document_type_hint: Optional[str] = None,
        document_date: Optional[str] = None,
        actor: str = "doctor",
        request_id: Optional[str] = None,
    ) -> Tuple[Document, bool]:
        # 1. Verify patient exists
        patient = db.query(Patient).filter(Patient.id == patient_id, Patient.deleted_at.is_(None)).first()
        if not patient:
            raise NotFoundError(f"Patient {patient_id} not found")

        # 2. Strict file validation (extension, magic bytes, MIME spoofing, corruption)
        detected_mime, safe_ext = validate_and_inspect_file(content, filename, declared_mime)

        # 3. Preprocess camera captures (EXIF orientation, downscale, contrast normalize)
        if uploaded_via == "camera" and detected_mime.startswith("image/"):
            content = preprocess_camera_image(content)

        file_size = len(content)

        # 4. SHA-256 deduplication per patient
        sha256 = compute_sha256(content)
        existing = db.query(Document).filter(
            Document.patient_id == patient_id, Document.sha256 == sha256
        ).first()
        if existing:
            # Check if a duplicate_record issue already exists for this document to avoid duplicate contradiction rows
            existing_issues = db.query(Contradiction).filter(
                Contradiction.patient_id == patient_id,
                Contradiction.issue_type == "duplicate_record",
                Contradiction.status == "open",
            ).all()
            already_flagged = any(existing.id in (iss.related_document_ids or "") for iss in existing_issues)
            if not already_flagged:
                issue = Contradiction(
                    id=contradiction_id(),
                    patient_id=patient_id,
                    issue_type="duplicate_record",
                    severity="low",
                    title="Duplicate Document Uploaded",
                    description=f"File '{filename}' matches existing document '{existing.original_filename}' (SHA256: {sha256[:12]}).",
                    related_document_ids=f'["{existing.id}"]',
                    related_fact_ids="[]",
                    detail_json=f'{{"sha256": "{sha256}"}}',
                    status="open",
                )
                db.add(issue)
                db.commit()
            return existing, True

        # 5. Store file on disk using secure random ID name (Never use user-provided filename as path!)
        doc_id = generate_doc_id()
        safe_display_name = sanitize_display_filename(filename)
        storage_filename = f"{doc_id}{safe_ext}"
        subfolder = "images" if uploaded_via == "camera" else "documents"

        patient_storage_dir = (settings.storage_path / "patients" / patient_id / subfolder).resolve()
        patient_storage_dir.mkdir(parents=True, exist_ok=True)

        stored_file_path = (patient_storage_dir / storage_filename).resolve()
        # Verify directory isolation (prevent path traversal)
        if not stored_file_path.is_relative_to(settings.storage_path.resolve()):
            raise BadRequestError("Path traversal detected in storage path.")

        stored_file_path.write_bytes(content)

        try:
            # 6. Create Document database record
            doc = Document(
                id=doc_id,
                patient_id=patient_id,
                original_filename=safe_display_name,
                stored_path=str(stored_file_path),
                mime_type=detected_mime,
                file_size=file_size,
                sha256=sha256,
                page_count=1,
                document_type=document_type_hint or "unknown",
                processing_status="UPLOADED",
                uploaded_via=uploaded_via,
            )
            db.add(doc)

            # 7. Create processing job in UPLOADED state
            job = ProcessingJob(
                id=generate_job_id(),
                subject_type="document",
                subject_id=doc_id,
                stage="UPLOADED",
                status="UPLOADED",
                attempts=0,
            )
            db.add(job)

            write_audit(
                db,
                actor=actor,
                action="document.uploaded",
                entity_type="document",
                entity_id=doc_id,
                patient_id=patient_id,
                after={"filename": safe_display_name, "mime": detected_mime, "size": file_size},
                request_id=request_id,
            )

            db.commit()
            db.refresh(doc)
            return doc, False
        except Exception:
            db.rollback()
            # Clean up the newly written file if another concurrent upload won the race
            try:
                if stored_file_path.exists():
                    stored_file_path.unlink()
            except Exception:
                pass
            existing = db.query(Document).filter(
                Document.patient_id == patient_id, Document.sha256 == sha256
            ).first()
            if existing:
                return existing, True
            raise

    @staticmethod
    def get(db: Session, document_id: str) -> Document:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise NotFoundError(f"Document {document_id} not found")
        return doc

    @staticmethod
    def list_by_patient(db: Session, patient_id: str) -> List[Document]:
        return (
            db.query(Document)
            .filter(Document.patient_id == patient_id)
            .order_by(Document.created_at.desc())
            .all()
        )

    @staticmethod
    def get_page(db: Session, document_id: str, page_number: int) -> DocumentPage:
        page = (
            db.query(DocumentPage)
            .filter(DocumentPage.document_id == document_id, DocumentPage.page_number == page_number)
            .first()
        )
        if not page:
            raise NotFoundError(f"Page {page_number} for document {document_id} not found")
        return page

    @staticmethod
    def find_stale_jobs(db: Session, max_age_seconds: int = 300) -> List[dict]:
        """Identifies active in-flight processing jobs that have not progressed within max_age_seconds."""
        import datetime
        now = datetime.datetime.now(datetime.UTC)
        cutoff = now - datetime.timedelta(seconds=max_age_seconds)

        active_statuses = ["PROCESSING", "EXTRACTING", "VALIDATING", "QUEUED", "processing", "in_progress", "retrying"]
        stale_jobs = (
            db.query(ProcessingJob)
            .filter(
                ProcessingJob.subject_type == "document",
                ProcessingJob.status.in_(active_statuses),
                (ProcessingJob.started_at < cutoff) | (ProcessingJob.created_at < cutoff),
            )
            .all()
        )

        results = []
        seen_doc_ids = set()
        for j in stale_jobs:
            seen_doc_ids.add(j.subject_id)
            ref_time = j.started_at or j.created_at
            if ref_time:
                age = (now - (ref_time.replace(tzinfo=datetime.UTC) if ref_time.tzinfo is None else ref_time)).total_seconds()
            else:
                age = 0.0
            results.append({
                "document_id": j.subject_id,
                "job_id": j.id,
                "status": str(j.status),
                "stage": str(j.stage),
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "attempts": j.attempts,
                "age_seconds": round(age, 1),
            })

        stale_docs = (
            db.query(Document)
            .filter(
                Document.processing_status.in_(["PROCESSING", "EXTRACTING", "VALIDATING", "QUEUED"]),
                Document.updated_at < cutoff,
            )
            .all()
        )
        for d in stale_docs:
            if d.id not in seen_doc_ids:
                ref_time = d.updated_at or d.created_at
                if ref_time:
                    age = (now - (ref_time.replace(tzinfo=datetime.UTC) if ref_time.tzinfo is None else ref_time)).total_seconds()
                else:
                    age = 0.0
                results.append({
                    "document_id": d.id,
                    "job_id": None,
                    "status": str(d.processing_status),
                    "stage": str(d.processing_status),
                    "started_at": d.created_at.isoformat() if d.created_at else None,
                    "attempts": 1,
                    "age_seconds": round(age, 1),
                })

        return results

    @staticmethod
    def mark_stale_jobs_as_failed(db: Session, max_age_seconds: int = 300) -> List[str]:
        """Transitions stale active processing jobs into FAILED status so no document is stuck in PROCESSING."""
        import datetime
        stale_records = DocumentService.find_stale_jobs(db, max_age_seconds=max_age_seconds)
        recovered_doc_ids = []
        now = datetime.datetime.now(datetime.UTC)

        for rec in stale_records:
            doc_id = rec["document_id"]
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc and doc.processing_status in ["PROCESSING", "EXTRACTING", "VALIDATING", "QUEUED", "processing"]:
                doc.processing_status = "FAILED"
                doc.processing_error_code = "STALE_PROCESSING_TIMEOUT"
                recovered_doc_ids.append(doc_id)

            if rec.get("job_id"):
                job = db.query(ProcessingJob).filter(ProcessingJob.id == rec["job_id"]).first()
                if job:
                    job.status = "FAILED"
                    job.stage = "FAILED"
                    job.finished_at = now
                    job.last_error_code = "STALE_PROCESSING_TIMEOUT"
                    job.last_error_detail = (
                        f"Job timed out after exceeding stale limit ({max_age_seconds}s) or worker was interrupted."
                    )
            else:
                job = ProcessingJob(
                    id=generate_job_id(),
                    subject_type="document",
                    subject_id=doc_id,
                    stage="FAILED",
                    status="FAILED",
                    attempts=1,
                    finished_at=now,
                    last_error_code="STALE_PROCESSING_TIMEOUT",
                    last_error_detail=f"Document found in active state exceeding stale limit ({max_age_seconds}s).",
                )
                db.add(job)

        if recovered_doc_ids:
            db.commit()
        return recovered_doc_ids

    @staticmethod
    def recover_document(
        db: Session,
        document_id: str,
        background_tasks: Optional[Any] = None,
        actor: str = "system",
    ) -> Document:
        """Safely reset and re-run a failed or stale document processing job."""
        from app.services.task_worker import task_worker
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise NotFoundError(f"Document {document_id} not found")

        doc.processing_status = "QUEUED"
        doc.processing_error_code = None

        job = (
            db.query(ProcessingJob)
            .filter(ProcessingJob.subject_id == document_id, ProcessingJob.subject_type == "document")
            .order_by(ProcessingJob.created_at.desc())
            .first()
        )
        if not job or job.status == "FAILED":
            job = ProcessingJob(
                id=generate_job_id(),
                subject_type="document",
                subject_id=document_id,
                stage="QUEUED",
                status="QUEUED",
                attempts=0,
            )
            db.add(job)
        else:
            job.stage = "QUEUED"
            job.status = "QUEUED"
            job.last_error_code = None
            job.last_error_detail = None

        write_audit(
            db,
            actor=actor,
            action="document.recovered",
            entity_type="document",
            entity_id=doc.id,
            patient_id=doc.patient_id,
            after={"status": "QUEUED", "recovered": True},
        )
        db.commit()
        db.refresh(doc)

        if background_tasks is not None:
            background_tasks.add_task(task_worker.process_document_async, document_id=doc.id, is_reprocess=True)

        return doc

    @staticmethod
    def recover_stale_jobs(
        db: Session,
        max_age_seconds: int = 300,
        background_tasks: Optional[Any] = None,
    ) -> List[str]:
        """Identifies stale jobs, marks them, and initiates recovery."""
        stale_doc_ids = DocumentService.mark_stale_jobs_as_failed(db, max_age_seconds=max_age_seconds)
        for doc_id in stale_doc_ids:
            DocumentService.recover_document(db, doc_id, background_tasks=background_tasks)
        return stale_doc_ids
