from sqlalchemy import Column, ForeignKey, String, Text, Index
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.models.base import TimestampMixin
from app.utils.ids import brief_id


class Brief(Base, TimestampMixin):
    __tablename__ = "briefs"

    id = Column(String(32), primary_key=True, default=brief_id)
    patient_id = Column(String(32), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    specialty = Column(String(64), default="general_medicine", nullable=False)
    content_json = Column(Text, nullable=False)
    generation_model = Column(String(128), nullable=True)
    generation_source = Column(String(32), default="llm", nullable=False)  # llm | fallback | fallback_template
    validation_report_id = Column(String(32), ForeignKey("validation_reports.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(32), default="validated", nullable=False)  # validated | validated_with_flags | fallback_template
    input_fingerprint = Column(String(64), nullable=False)

    __table_args__ = (
        Index("ix_briefs_patient_created", "patient_id", "created_at"),
    )

    patient = relationship("Patient", back_populates="briefs")
    validation_report = relationship("ValidationReport", foreign_keys=[validation_report_id])
