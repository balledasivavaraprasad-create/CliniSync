from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.models.base import TimestampMixin
from app.utils.ids import document_id, page_id


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
    processing_status = Column(String(32), default="uploaded", nullable=False, index=True)
    processing_error_code = Column(String(64), nullable=True)
    extracted_text_path = Column(String(512), nullable=True)
    ocr_method = Column(String(32), default="pdf_text", nullable=False)
    is_fallback = Column(Boolean, default=False, nullable=False)
    uploaded_via = Column(String(32), default="upload", nullable=False)

    __table_args__ = (
        UniqueConstraint("patient_id", "sha256", name="uq_patient_doc_sha256"),
    )

    pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan")


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id = Column(String(32), primary_key=True, default=page_id)
    document_id = Column(String(32), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number = Column(Integer, nullable=False)
    text = Column(Text, nullable=False, default="")
    ocr_confidence = Column(Float, default=1.0, nullable=False)
    method = Column(String(32), default="pdf_text", nullable=False)

    document = relationship("Document", back_populates="pages")
