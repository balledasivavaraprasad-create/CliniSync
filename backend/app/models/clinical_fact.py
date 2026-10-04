from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from app.db.database import Base
from app.models.base import TimestampMixin
from app.utils.ids import fact_id


class ClinicalFact(Base, TimestampMixin):
    __tablename__ = "clinical_facts"

    id = Column(String(32), primary_key=True, default=fact_id)
    patient_id = Column(String(32), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(32), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    voice_note_id = Column(String(32), nullable=True)
    fact_type = Column(String(64), nullable=False, index=True)
    value = Column(Text, nullable=False)
    normalized_value = Column(Text, nullable=True)  # JSON serialized
    fact_date = Column(DateTime, nullable=True)
    confidence = Column(Float, default=1.0, nullable=False)
    confidence_band = Column(String(32), default="high", nullable=False)
    source_text = Column(Text, nullable=False)
    source_page = Column(Integer, nullable=True)
    source_span_start = Column(Integer, nullable=True)
    source_span_end = Column(Integer, nullable=True)
    provenance_verified = Column(Boolean, default=False, nullable=False)
    verification_status = Column(String(32), default="unverified", nullable=False)
    extraction_model = Column(String(128), nullable=True)
    extraction_run_id = Column(String(64), nullable=True)
