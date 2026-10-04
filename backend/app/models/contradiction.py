from sqlalchemy import Column, ForeignKey, String, Text
from app.db.database import Base
from app.models.base import TimestampMixin
from app.utils.ids import contradiction_id


class Contradiction(Base, TimestampMixin):
    __tablename__ = "contradictions"

    id = Column(String(32), primary_key=True, default=contradiction_id)
    patient_id = Column(String(32), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    issue_type = Column(String(64), nullable=False, index=True)
    severity = Column(String(32), default="medium", nullable=False)  # low | medium | high
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    related_document_ids = Column(Text, default="[]", nullable=False)  # JSON list
    related_fact_ids = Column(Text, default="[]", nullable=False)  # JSON list
    detail_json = Column(Text, default="{}", nullable=False)
    status = Column(String(32), default="open", nullable=False, index=True)  # open | acknowledged | resolved_by_doctor | dismissed
    doctor_note = Column(Text, nullable=True)
    detected_run_id = Column(String(64), nullable=True)
