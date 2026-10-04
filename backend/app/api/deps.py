from typing import Generator
from fastapi import Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.database import get_db


class CurrentUser(BaseModel):
    id: str = "doc_001"
    name: str = "Dr. Willie Carter, MD"
    role: str = "doctor"
    specialty: str = "general_medicine"


def get_current_user() -> CurrentUser:
    """Stubbed authentication returning default clinical user"""
    return CurrentUser()


def get_db_session(db: Session = Depends(get_db)) -> Generator[Session, None, None]:
    yield db


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "req_direct")


def resolve_patient_id(patient_id: str) -> str:
    if patient_id in ("demo-patient-001", "demo_patient_001"):
        return "pat_demo_patient_001"
    return patient_id

