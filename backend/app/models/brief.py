from sqlalchemy import Column, ForeignKey, String, Text
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
    validation_report_id = Column(String(32), nullable=True)
    status = Column(String(32), default="validated", nullable=False)  # validated | validated_with_flags | fallback_template
    input_fingerprint = Column(String(64), nullable=False)
