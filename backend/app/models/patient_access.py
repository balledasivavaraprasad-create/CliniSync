from sqlalchemy import Column, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.models.base import TimestampMixin
from app.utils.ids import generate_id


def patient_access_id() -> str:
    return generate_id("acc")


class PatientAccess(Base, TimestampMixin):
    """Explicit authorization granting a user permission to access a patient."""
    __tablename__ = "patient_access"

    id = Column(String(32), primary_key=True, default=patient_access_id)
    user_id = Column(String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(String(32), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    access_level = Column(String(32), default="read_write", nullable=False)  # read, read_write, primary_doctor

    __table_args__ = (
        UniqueConstraint("user_id", "patient_id", name="uq_user_patient_access"),
    )

    patient = relationship("Patient", back_populates="patient_accesses")
    user = relationship("User")
