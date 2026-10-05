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


def require_patient_id(db: Session, patient_id: str) -> str:
    """Resolve aliases and verify the patient exists, else raise 404.

    Most patient-scoped endpoints previously resolved an alias and queried
    straight away, so an unknown id returned `200 []` — indistinguishable from a
    patient with genuinely no records. The Flutter client shows different UI for
    the two cases (docs/frontend/API_MISMATCHES.md M-17), so it now gets a real
    `404 NOT_FOUND`.
    """
    from app.api.errors import NotFoundError
    from app.models.patient import Patient

    pid = resolve_patient_id(patient_id)
    found = db.query(Patient.id).filter(
        Patient.id == pid,
        Patient.deleted_at.is_(None),
    ).first()
    if found:
        return pid

    # Last resort, matching PatientService.get: any demo patient.
    if patient_id in ("demo-patient-001", "pat_demo_patient_001"):
        demo = db.query(Patient.id).filter(
            Patient.is_demo == True,  # noqa: E712 — SQLAlchemy needs ==
            Patient.deleted_at.is_(None),
        ).first()
        if demo:
            return demo[0] if isinstance(demo, tuple) else demo.id

    raise NotFoundError(f"No patient with id {patient_id}")

