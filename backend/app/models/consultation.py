from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.models.base import TimestampMixin
from app.utils.ids import consultation_id, version_id


class Consultation(Base, TimestampMixin):
    __tablename__ = "consultations"

    id = Column(String(32), primary_key=True, default=consultation_id)
    patient_id = Column(String(32), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    brief_id = Column(String(32), nullable=True)
    specialty = Column(String(64), default="general_medicine", nullable=False)
    status = Column(String(32), default="draft", nullable=False)  # draft | in_review | approved
    current_version_id = Column(String(32), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(String(128), nullable=True)

    versions = relationship("ConsultationVersion", back_populates="consultation", cascade="all, delete-orphan")


class ConsultationVersion(Base, TimestampMixin):
    __tablename__ = "consultation_versions"

    id = Column(String(32), primary_key=True, default=version_id)
    consultation_id = Column(String(32), ForeignKey("consultations.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, default=1, nullable=False)
    origin = Column(String(32), default="ai_generated", nullable=False)  # ai_generated | doctor_edited | approved
    content_json = Column(Text, nullable=False)
    change_summary = Column(String(255), nullable=True)
    edited_by = Column(String(128), nullable=True)
    validation_report_id = Column(String(32), nullable=True)

    consultation = relationship("Consultation", back_populates="versions")
