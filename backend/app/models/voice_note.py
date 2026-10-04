from sqlalchemy import Column, Float, ForeignKey, String, Text
from app.db.database import Base
from app.models.base import TimestampMixin
from app.utils.ids import voice_note_id


class VoiceNote(Base, TimestampMixin):
    __tablename__ = "voice_notes"

    id = Column(String(32), primary_key=True, default=voice_note_id)
    patient_id = Column(String(32), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    stored_path = Column(String(512), nullable=False)
    duration_s = Column(Float, default=0.0, nullable=False)
    transcript_raw = Column(Text, nullable=False, default="")
    transcript_normalized = Column(Text, nullable=True)
    stt_model = Column(String(128), nullable=True)
    stt_confidence = Column(Float, default=1.0, nullable=False)
    language = Column(String(32), default="en", nullable=False)
    status = Column(String(32), default="uploaded", nullable=False)
    review_status = Column(String(32), default="pending_review", nullable=False)  # pending_review | reviewed
