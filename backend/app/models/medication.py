from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Index
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.models.base import TimestampMixin
from app.utils.ids import medication_id


class Medication(Base, TimestampMixin):
    __tablename__ = "medications"

    id = Column(String(32), primary_key=True, default=medication_id)
    patient_id = Column(String(32), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    fact_id = Column(String(32), ForeignKey("clinical_facts.id", ondelete="CASCADE"), nullable=False, index=True)
    canonical_name = Column(String(255), nullable=False)
    raw_name = Column(String(255), nullable=False)
    strength_value = Column(Float, nullable=True)
    strength_unit = Column(String(32), nullable=True)
    dose_text = Column(String(128), nullable=True)
    frequency_code = Column(String(32), default="other", nullable=False)
    frequency_text = Column(String(128), nullable=True)
    route = Column(String(64), nullable=True)
    duration_text = Column(String(128), nullable=True)
    start_date = Column(DateTime, nullable=True)
    stop_date = Column(DateTime, nullable=True)
    status = Column(String(32), default="current", nullable=False)  # current | previous | uncertain
    status_reason = Column(String(255), nullable=True)
    group_key = Column(String(255), nullable=False, index=True)  # patient_id + canonical_name
    confidence = Column(Float, default=1.0, nullable=False)
    source_document_id = Column(String(32), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)

    __table_args__ = (
        Index("ix_medications_patient_status", "patient_id", "status"),
    )

    patient = relationship("Patient", back_populates="medications")
    fact = relationship("ClinicalFact", back_populates="medications")
    source_document = relationship("Document", foreign_keys=[source_document_id])

    @property
    def semantic_state(self) -> str:
        if self.fact and hasattr(self.fact, "semantic_state"):
            return self.fact.semantic_state
        return "DOCUMENTED" if self.confidence >= 0.85 else "UNVERIFIED"

    @property
    def dose_semantic_state(self) -> str:
        return "DOCUMENTED" if (self.dose_text or self.strength_value is not None) else "MISSING"
