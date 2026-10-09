from sqlalchemy import Column, DateTime, ForeignKey, String, Text, Index
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.models.base import TimestampMixin
from app.utils.ids import timeline_event_id


class TimelineEvent(Base, TimestampMixin):
    __tablename__ = "timeline_events"

    id = Column(String(32), primary_key=True, default=timeline_event_id)
    patient_id = Column(String(32), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    event_date = Column(DateTime, nullable=True)
    date_precision = Column(String(32), default="day", nullable=False)  # day | month | year | unknown
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=False)
    related_fact_ids = Column(Text, default="[]", nullable=False)  # JSON list
    source_document_id = Column(String(32), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    sort_key = Column(String(64), nullable=False, index=True)

    __table_args__ = (
        Index("ix_timeline_events_patient_date", "patient_id", "event_date"),
    )

    patient = relationship("Patient", back_populates="timeline_events")
    source_document = relationship("Document", foreign_keys=[source_document_id])

    @property
    def semantic_state(self) -> str:
        if self.source_document_id or self.event_date:
            return "DOCUMENTED"
        return "UNVERIFIED"

    @property
    def status(self) -> str:
        return self.semantic_state
