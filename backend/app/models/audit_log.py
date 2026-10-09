from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from app.db.database import Base
from app.models.base import TimestampMixin, utc_now
from app.utils.ids import audit_id, llm_log_id


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String(32), primary_key=True, default=audit_id)
    timestamp = Column(DateTime, default=utc_now, nullable=False, index=True)
    actor = Column(String(128), default="doctor", nullable=False)
    action = Column(String(128), nullable=False)
    entity_type = Column(String(64), nullable=False, index=True)
    entity_id = Column(String(64), nullable=False, index=True)
    patient_id = Column(String(32), ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True)
    before_json = Column(Text, nullable=True)
    after_json = Column(Text, nullable=True)
    request_id = Column(String(64), nullable=True)
    ip = Column(String(64), nullable=True)


class LLMCallLog(Base):
    __tablename__ = "llm_call_log"

    id = Column(String(32), primary_key=True, default=llm_log_id)
    request_id = Column(String(64), nullable=True, index=True)
    task = Column(String(64), nullable=False)
    logical_slot = Column(String(64), nullable=False)
    provider_model_used = Column(String(128), nullable=False)
    fallback_depth = Column(Integer, default=0, nullable=False)
    latency_ms = Column(Float, default=0.0, nullable=False)
    input_tokens = Column(Integer, default=0, nullable=False)
    output_tokens = Column(Integer, default=0, nullable=False)
    success = Column(Boolean, default=True, nullable=False)
    error_code = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
