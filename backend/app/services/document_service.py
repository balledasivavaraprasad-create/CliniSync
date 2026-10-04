import os
import re
from pathlib import Path
from typing import List, Optional, Tuple
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
)
from app.services.audit_service import write_audit


def sanitize_filename(filename: str) -> str:
    clean = os.path.basename(filename)
    clean = re.sub(r"[^\w\.-]", "_", clean)
    return clean or "document.bin"


def preprocess_camera_image(content: bytes) -> bytes:
    """Preprocess camera uploads: EXIF auto-orient, max dimension downscale, autocontrast normalize."""
    import io
    from PIL import Image, ImageOps

    try:
        img = Image.open(io.BytesIO(content))
        # 1. EXIF auto-orientation
        img = ImageOps.exif_transpose(img)

        # 2. Downscale to safe max dimension if large
        max_dim = 2048
        if img.width > max_dim or img.height > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        # 3. Contrast normalize if RGB / L
        if img.mode in ("RGB", "L"):
            img = ImageOps.autocontrast(img, cutoff=0.5)

        out_io = io.BytesIO()
        fmt = img.format if img.format in ("JPEG", "PNG", "WEBP") else "JPEG"
        if fmt == "JPEG" and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(out_io, format=fmt, quality=90)
        return out_io.getvalue()
    except Exception:
        # Fallback to original bytes if image parsing fails
        return content



def detect_mime_type(content: bytes, declared_mime: str) -> str:
    """Validate MIME magic bytes to ensure safe files"""
    if content.startswith(b"%PDF"):
        return "application/pdf"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(content) > 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if content.startswith(b"ID3") or content.startswith(b"\xff\xfb"):
        return "audio/mpeg"
    if len(content) > 12 and content[:4] == b"RIFF" and content[8:12] == b"WAVE":
        return "audio/wav"
    return declared_mime


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

        # 2. Check file size
        file_size = len(content)
        max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
        if file_size > max_bytes:
            raise FileTooLargeError(f"File size {file_size} exceeds max {max_bytes} bytes")

        # 3. MIME magic validation
        detected_mime = detect_mime_type(content, declared_mime)
        if detected_mime not in settings.allowed_mime_list:
            raise UnsupportedFileTypeError(f"MIME type '{detected_mime}' is not permitted.")

        # Preprocess camera captures (EXIF auto-orient, downscale, contrast normalize per Section 14)
        if uploaded_via == "camera" and detected_mime.startswith("image/"):
            content = preprocess_camera_image(content)
            file_size = len(content)

        # 4. SHA-256 deduplication per patient
        sha256 = compute_sha256(content)
        existing = db.query(Document).filter(Document.patient_id == patient_id, Document.sha256 == sha256).first()
        if existing:
            # Create duplicate_record issue per Section 7 & 11.5
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

        # 5. Store file on disk
        doc_id = generate_doc_id()
        safe_name = sanitize_filename(filename)
        subfolder = "images" if uploaded_via == "camera" else "documents"
        patient_storage_dir = settings.storage_path / "patients" / patient_id / subfolder
        patient_storage_dir.mkdir(parents=True, exist_ok=True)

        stored_file_path = patient_storage_dir / f"{doc_id}__{safe_name}"
        stored_file_path.write_bytes(content)

        # 6. Create Document record
        doc = Document(
            id=doc_id,
            patient_id=patient_id,
            original_filename=safe_name,
            stored_path=str(stored_file_path),
            mime_type=detected_mime,
            file_size=file_size,
            sha256=sha256,
            page_count=1,
            document_type=document_type_hint or "unknown",
            processing_status="uploaded",
            uploaded_via=uploaded_via,
        )
        db.add(doc)

        # 7. Create processing job
        job = ProcessingJob(
            id=generate_job_id(),
            subject_type="document",
            subject_id=doc_id,
            stage="uploaded",
            status="pending",
        )
        db.add(job)

        write_audit(
            db,
            actor=actor,
            action="document.uploaded",
            entity_type="document",
            entity_id=doc_id,
            patient_id=patient_id,
            after={"filename": safe_name, "mime": detected_mime, "size": file_size},
            request_id=request_id,
        )

        db.commit()
        db.refresh(doc)
        return doc, False

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
