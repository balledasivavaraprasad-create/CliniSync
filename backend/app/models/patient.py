from sqlalchemy import Boolean, Column, DateTime, Integer, String
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
    is_demo = Column(Boolean, default=False, nullable=False)
    last_activity_at = Column(DateTime, default=utc_now, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
