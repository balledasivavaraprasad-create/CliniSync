from sqlalchemy import Column, DateTime, Integer, String, Text
from app.db.database import Base
from app.models.base import TimestampMixin
from app.utils.ids import job_id


class ProcessingJob(Base, TimestampMixin):
    __tablename__ = "processing_jobs"

    id = Column(String(32), primary_key=True, default=job_id)
    subject_type = Column(String(32), nullable=False)  # document | voice | brief
    subject_id = Column(String(32), nullable=False, index=True)
    stage = Column(String(64), nullable=False)
    status = Column(String(32), default="pending", nullable=False)  # pending | in_progress | completed | failed
    attempts = Column(Integer, default=0, nullable=False)
    last_error_code = Column(String(64), nullable=True)
    last_error_detail = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
