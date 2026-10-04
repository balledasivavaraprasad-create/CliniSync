from sqlalchemy import Boolean, Column, ForeignKey, String, Text
from app.db.database import Base
from app.models.base import TimestampMixin
from app.utils.ids import memory_id


class ClinicalMemory(Base, TimestampMixin):
    __tablename__ = "clinical_memory"

    id = Column(String(32), primary_key=True, default=memory_id)
    patient_id = Column(String(32), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    memory_type = Column(String(64), nullable=False)  # diagnosis | medication | allergy | history | investigation_summary | plan_note
    content_json = Column(Text, nullable=False)
    source_consultation_id = Column(String(32), ForeignKey("consultations.id", ondelete="SET NULL"), nullable=True)
    source_version_id = Column(String(32), nullable=True)
    verified = Column(Boolean, default=True, nullable=False)
    validation_report_id = Column(String(32), nullable=True)
    supersedes_id = Column(String(32), nullable=True)
