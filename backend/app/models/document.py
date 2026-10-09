from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Index
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.models.base import TimestampMixin
from app.utils.ids import document_id, page_id


class ProcessingStatusStr(str):
    """Case-tolerant string wrapper that equals both uppercase canonical and legacy lowercase strings."""
    def __eq__(self, other):
        if isinstance(other, str):
            s_up = self.upper()
            o_up = other.upper()
            if s_up == o_up:
                return True
            if s_up == "COMPLETED" and o_up in ("COMPLETE", "COMPLETED"):
                return True
            if s_up == "EXTRACTING" and o_up in ("EXTRACTING", "EXTRACTING_TEXT", "EXTRACTING_ENTITIES"):
                return True
            if s_up == "VALIDATING" and o_up in ("VALIDATING", "NORMALIZING"):
                return True
            if s_up == "PROCESSING" and o_up in ("PROCESSING", "IN_PROGRESS", "CLASSIFYING"):
                return True
            if s_up == "RETRY_PENDING" and o_up in ("RETRY_PENDING", "RETRYING"):
                return True
        return super().__eq__(other)

    def __hash__(self):
        return super().__hash__()


class ProcessingStatusType(TypeDecorator):
    impl = String(32)
    cache_ok = True

    _NORM_MAP = {
        "uploaded": "UPLOADED",
        "queued": "QUEUED",
        "processing": "PROCESSING",
        "in_progress": "PROCESSING",
        "classifying": "PROCESSING",
        "extracting": "EXTRACTING",
        "extracting_text": "EXTRACTING",
        "extracting_entities": "EXTRACTING",
        "normalizing": "VALIDATING",
        "validating": "VALIDATING",
        "complete": "COMPLETED",
        "completed": "COMPLETED",
        "failed": "FAILED",
        "retry_pending": "RETRY_PENDING",
        "retrying": "RETRY_PENDING",
        "needs_review": "COMPLETED",
    }

    def process_bind_param(self, value, dialect):
        if value is None:
            return "UPLOADED"
        s = str(value)
        return self._NORM_MAP.get(s.lower(), s.upper())

    def process_result_value(self, value, dialect):
        return ProcessingStatusStr(value) if value is not None else None


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id = Column(String(32), primary_key=True, default=document_id)
    patient_id = Column(String(32), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    stored_path = Column(String(512), nullable=False)
    mime_type = Column(String(128), nullable=False)
    file_size = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)
    page_count = Column(Integer, default=1, nullable=False)
    document_type = Column(String(64), default="unknown", nullable=False)
    document_date = Column(DateTime, nullable=True)
    classification_confidence = Column(Float, default=0.0, nullable=False)
    processing_status = Column(ProcessingStatusType, default="UPLOADED", nullable=False, index=True)
    processing_error_code = Column(String(64), nullable=True)
    extracted_text_path = Column(String(512), nullable=True)
    ocr_method = Column(String(32), default="pdf_text", nullable=False)
    is_fallback = Column(Boolean, default=False, nullable=False)
    uploaded_via = Column(String(32), default="upload", nullable=False)

    __table_args__ = (
        UniqueConstraint("patient_id", "sha256", name="uq_patient_doc_sha256"),
        Index("ix_documents_patient_status", "patient_id", "processing_status"),
    )

    patient = relationship("Patient", back_populates="documents")
    pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan")
    facts = relationship("ClinicalFact", back_populates="document", cascade="all, delete-orphan")


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id = Column(String(32), primary_key=True, default=page_id)
    document_id = Column(String(32), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number = Column(Integer, nullable=False)
    text = Column(Text, nullable=False, default="")
    ocr_confidence = Column(Float, default=1.0, nullable=False)
    method = Column(String(32), default="pdf_text", nullable=False)

    __table_args__ = (
        UniqueConstraint("document_id", "page_number", name="uq_doc_page_number"),
    )

    document = relationship("Document", back_populates="pages")
