from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.models.base import TimestampMixin, utc_now
from app.utils.ids import patient_id


class Patient(Base, TimestampMixin):
    __tablename__ = "patients"

    id = Column(String(32), primary_key=True, default=patient_id)
    full_name = Column(String(255), nullable=False, index=True)
    date_of_birth = Column(String(32), nullable=True)
    age_years = Column(Integer, nullable=True)
    sex = Column(String(16), nullable=True)
    contact_ref = Column(String(128), nullable=True)
    is_demo = Column(Boolean, default=False, nullable=False, index=True)
    last_activity_at = Column(DateTime, default=utc_now, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    documents = relationship("Document", back_populates="patient", cascade="all, delete-orphan")
    clinical_facts = relationship("ClinicalFact", back_populates="patient", cascade="all, delete-orphan")
    medications = relationship("Medication", back_populates="patient", cascade="all, delete-orphan")
    investigations = relationship("Investigation", back_populates="patient", cascade="all, delete-orphan")
    consultations = relationship("Consultation", back_populates="patient", cascade="all, delete-orphan")
    clinical_memories = relationship("ClinicalMemory", back_populates="patient", cascade="all, delete-orphan")
    patient_accesses = relationship("PatientAccess", back_populates="patient", cascade="all, delete-orphan")
    voice_notes = relationship("VoiceNote", back_populates="patient", cascade="all, delete-orphan")
    contradictions = relationship("Contradiction", back_populates="patient", cascade="all, delete-orphan")
    timeline_events = relationship("TimelineEvent", back_populates="patient", cascade="all, delete-orphan")
    briefs = relationship("Brief", back_populates="patient", cascade="all, delete-orphan")
