from sqlalchemy import Boolean, Column, String
from app.db.database import Base
from app.models.base import TimestampMixin
from app.utils.ids import user_id


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(String(32), primary_key=True, default=user_id)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(64), default="doctor", nullable=False, index=True)
    specialty = Column(String(128), default="Cardiology", nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    avatar_url = Column(String(255), nullable=True)
