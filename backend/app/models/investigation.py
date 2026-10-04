from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text
from app.db.database import Base
from app.models.base import TimestampMixin
from app.utils.ids import investigation_id


class Investigation(Base, TimestampMixin):
    __tablename__ = "investigations"

    id = Column(String(32), primary_key=True, default=investigation_id)
    patient_id = Column(String(32), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    fact_id = Column(String(32), ForeignKey("clinical_facts.id", ondelete="CASCADE"), nullable=False)
    test_name_raw = Column(String(255), nullable=False)
    test_name_canonical = Column(String(255), nullable=False)
    value_numeric = Column(Float, nullable=True)
    value_text = Column(String(255), nullable=False)
    unit = Column(String(64), nullable=True)
    reference_low = Column(Float, nullable=True)
    reference_high = Column(Float, nullable=True)
    reference_text = Column(String(255), nullable=True)
    abnormal_flag = Column(String(32), default="unknown", nullable=False)  # low | high | normal | unknown
    observed_date = Column(DateTime, nullable=True)
    source_document_id = Column(String(32), nullable=True)
    confidence = Column(Float, default=1.0, nullable=False)
    group_key = Column(String(255), nullable=False, index=True)
