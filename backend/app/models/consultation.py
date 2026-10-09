from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.models.base import TimestampMixin
from app.utils.ids import consultation_id, version_id


class Consultation(Base, TimestampMixin):
    __tablename__ = "consultations"

    id = Column(String(32), primary_key=True, default=consultation_id)
    patient_id = Column(String(32), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    brief_id = Column(String(32), ForeignKey("briefs.id", ondelete="SET NULL"), nullable=True, index=True)
    specialty = Column(String(64), default="general_medicine", nullable=False)
    status = Column(String(32), default="draft", nullable=False)  # draft | in_review | approved
    current_version_id = Column(String(32), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(String(128), nullable=True)

    __table_args__ = (
        Index("ix_consultations_patient_status", "patient_id", "status"),
    )

    patient = relationship("Patient", back_populates="consultations")
    brief = relationship("Brief", foreign_keys=[brief_id])
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
    validation_report_id = Column(String(32), ForeignKey("validation_reports.id", ondelete="SET NULL"), nullable=True, index=True)

    __table_args__ = (
        UniqueConstraint("consultation_id", "version_number", name="uq_consultation_version_num"),
    )

    consultation = relationship("Consultation", back_populates="versions")
    validation_report = relationship("ValidationReport", foreign_keys=[validation_report_id])
