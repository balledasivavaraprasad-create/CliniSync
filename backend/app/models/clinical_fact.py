from typing import Optional
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, Index
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.models.base import TimestampMixin
from app.utils.ids import fact_id


class ClinicalFact(Base, TimestampMixin):
    __tablename__ = "clinical_facts"

    id = Column(String(32), primary_key=True, default=fact_id)
    patient_id = Column(String(32), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(32), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    voice_note_id = Column(String(32), ForeignKey("voice_notes.id", ondelete="SET NULL"), nullable=True, index=True)
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

    __table_args__ = (
        Index("ix_clinical_facts_patient_fact_type", "patient_id", "fact_type"),
        Index("ix_clinical_facts_patient_date", "patient_id", "fact_date"),
    )

    patient = relationship("Patient", back_populates="clinical_facts")
    document = relationship("Document", back_populates="facts")
    voice_note = relationship("VoiceNote", back_populates="clinical_facts")
    medications = relationship("Medication", back_populates="fact", cascade="all, delete-orphan")
    investigations = relationship("Investigation", back_populates="fact", cascade="all, delete-orphan")

    @property
    def semantic_state(self) -> str:
        if self.verification_status:
            s = self.verification_status.upper()
            if s in ("DOCUMENTED", "DOCTOR_VERIFIED"):
                return "DOCUMENTED"
            if s in ("INFERRED",):
                return "INFERRED"
            if s in ("CONFLICTING",):
                return "CONFLICTING"
            if s in ("MISSING",):
                return "MISSING"
            if s in ("UNKNOWN",):
                return "UNKNOWN"
            if s in ("UNVERIFIED", "NEEDS_VERIFICATION"):
                return "DOCUMENTED" if self.provenance_verified else "UNVERIFIED"
        return "DOCUMENTED" if self.provenance_verified else "UNVERIFIED"

    @semantic_state.setter
    def semantic_state(self, val: str) -> None:
        self.verification_status = val

    @property
    def source_span(self) -> Optional[dict]:
        if self.source_span_start is not None or self.source_span_end is not None:
            return {"start": self.source_span_start, "end": self.source_span_end}
        return None

    @property
    def extraction_method(self) -> str:
        return self.extraction_model or "ai_extraction"

    @property
    def verification_timestamp(self) -> Optional[str]:
        if self.updated_at:
            return self.updated_at.isoformat()
        if self.created_at:
            return self.created_at.isoformat()
        return None

    @property
    def confidence_explanation(self) -> Optional[dict]:
        if self.normalized_value:
            try:
                import json
                data = json.loads(self.normalized_value)
                if isinstance(data, dict):
                    return data.get("confidence_explanation")
            except Exception:
                pass
        return None

    @property
    def status(self) -> str:
        return self.semantic_state

    @status.setter
    def status(self, val: str) -> None:
        self.semantic_state = val
