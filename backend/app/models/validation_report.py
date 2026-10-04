from sqlalchemy import Column, Integer, String, Text
from app.db.database import Base
from app.models.base import TimestampMixin
from app.utils.ids import report_id


class ValidationReport(Base, TimestampMixin):
    __tablename__ = "validation_reports"

    id = Column(String(32), primary_key=True, default=report_id)
    gate = Column(String(32), nullable=False)  # gate1_memory | gate2_output
    subject_type = Column(String(32), nullable=False)  # brief | consultation | fact
    subject_id = Column(String(32), nullable=False, index=True)
    outcome = Column(String(32), nullable=False)  # pass | pass_with_flags | blocked
    checks_json = Column(Text, nullable=False, default="[]")
    judge_model = Column(String(128), nullable=True)
    judge_verdict_json = Column(Text, nullable=True)
    attempt_number = Column(Integer, default=1, nullable=False)
