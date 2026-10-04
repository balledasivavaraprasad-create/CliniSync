from sqlalchemy import Column, DateTime, Float, ForeignKey, String
from app.db.database import Base
from app.models.base import TimestampMixin
from app.utils.ids import medication_id


class Medication(Base, TimestampMixin):
    __tablename__ = "medications"

    id = Column(String(32), primary_key=True, default=medication_id)
    patient_id = Column(String(32), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    fact_id = Column(String(32), ForeignKey("clinical_facts.id", ondelete="CASCADE"), nullable=False)
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
    source_document_id = Column(String(32), nullable=True)
