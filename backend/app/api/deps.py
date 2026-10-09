from typing import Generator, Optional, List
from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from jose import JWTError

from app.config import settings
from app.db.database import get_db
from app.api.errors import UnauthorizedError, ForbiddenError, NotFoundError
from app.models.user import User
from app.models.patient import Patient
from app.models.patient_access import PatientAccess
from app.utils.tokens import decode_access_token


class CurrentUser(BaseModel):
    id: str
    name: str
    email: str = ""
    role: str = "doctor"
    specialty: str = "general_medicine"

    @property
    def is_admin(self) -> bool:
        return self.role.lower() in ("admin", "administrator")

    @property
    def is_clinical(self) -> bool:
        return self.role.lower() in ("doctor", "physician", "nurse", "clinician", "admin")


# Auto-error=False so we can handle missing tokens explicitly and support isolated demo fallback when enabled
security_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """Resolve the authenticated clinical user from the JWT Bearer token."""
    token: Optional[str] = None
    if credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials.strip()

    if token:
        try:
            payload = decode_access_token(token)
            user_id: str = payload.get("sub")
            if not user_id:
                raise UnauthorizedError("Invalid token payload: missing subject.")
        except JWTError as exc:
            raise UnauthorizedError(f"Authentication failed: {str(exc)}")

        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        if not user:
            raise UnauthorizedError("User does not exist or has been deactivated.")

        request.state.user_id = user.id
        return CurrentUser(
            id=user.id,
            name=user.full_name,
            email=user.email,
            role=user.role,
            specialty=user.specialty,
        )

    # If no token is provided:
    if settings.AUTH_DEMO_FALLBACK_ENABLED:
        # Isolated demo fallback for local dev/testing
        user = db.query(User).filter(User.is_active == True).first()
        if user:
            request.state.user_id = user.id
            return CurrentUser(
                id=user.id,
                name=user.full_name,
                email=user.email,
                role=user.role,
                specialty=user.specialty,
            )
        request.state.user_id = "usr_doctor_001"
        return CurrentUser(
            id="usr_doctor_001",
            name="Dr. Willie Carter, MD",
            email="doctor@clinsync.health",
            role="doctor",
            specialty="General Medicine",
        )

    raise UnauthorizedError("Authentication required: missing Bearer token.")


def require_role(*allowed_roles: str):
    """Enforce role-based access control (e.g. require_role('admin'), require_role('doctor', 'admin'))."""
    def role_checker(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        normalized_allowed = [r.lower() for r in allowed_roles]
        if current_user.role.lower() not in normalized_allowed and not current_user.is_admin:
            raise ForbiddenError(f"Role '{current_user.role}' is not authorized to perform this action.")
        return current_user
    return role_checker


def get_accessible_patient_ids(db: Session, user: CurrentUser) -> Optional[set]:
    """Return a set of patient IDs accessible to the user, or None if the user has unrestricted (admin) access."""
    if user.is_admin:
        return None

    if user.role.lower() == "patient":
        # A patient user can only access records specifically assigned to them
        assigned = {
            pid for (pid,) in db.query(PatientAccess.patient_id).filter(PatientAccess.user_id == user.id).all()
        }
        return assigned

    # For clinical users:
    user_assigned_pids = {
        pid for (pid,) in db.query(PatientAccess.patient_id).filter(PatientAccess.user_id == user.id).all()
    }
    demo_pids = {
        pid for (pid,) in db.query(Patient.id).filter(Patient.is_demo == True, Patient.deleted_at.is_(None)).all()
    }
    all_restricted_pids = {
        pid for (pid,) in db.query(PatientAccess.patient_id).distinct().all()
    }
    unrestricted_pids = (
        {pid for (pid,) in db.query(Patient.id).filter(~Patient.id.in_(all_restricted_pids), Patient.deleted_at.is_(None)).all()}
        if (user.is_clinical and getattr(settings, "DEMO_FALLBACKS_ENABLED", True) and settings.APP_ENV == "development")
        else set()
    )
    return user_assigned_pids | demo_pids | unrestricted_pids


def check_patient_authorization(db: Session, user: CurrentUser, patient_id: str) -> bool:
    """Check if the user has permission to access the patient.

    Rules:
    1. Admins have access to all patients.
    2. Patient role users can ONLY access patients explicitly assigned to their user account.
    3. Clinical users have access to demo patients (is_demo == True).
    4. If explicit PatientAccess records exist in the system for this patient,
       the clinical user must have an explicit PatientAccess record for this patient.
    5. In production, explicit PatientAccess is mandatory (fail-closed).
    6. In dev mode without explicit assignments, clinical users have access if demo fallback is enabled.
    """
    if user.is_admin:
        return True

    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        return False

    # 1. Patients can only access their explicitly assigned patient record
    if user.role.lower() == "patient":
        user_access = db.query(PatientAccess.id).filter(
            PatientAccess.patient_id == patient_id,
            PatientAccess.user_id == user.id,
        ).first()
        return user_access is not None

    # 2. Demo patients accessible to clinical users
    if patient.is_demo and user.is_clinical:
        return True

    # 3. Check if this patient has specific access assignments
    has_assignments = db.query(PatientAccess.id).filter(PatientAccess.patient_id == patient_id).first() is not None
    if has_assignments:
        user_access = db.query(PatientAccess.id).filter(
            PatientAccess.patient_id == patient_id,
            PatientAccess.user_id == user.id,
        ).first()
        return user_access is not None

    # 4. In non-development mode: explicit PatientAccess is mandatory (fail-closed)
    if settings.APP_ENV != "development":
        return False

    # 5. Fallback in dev: clinical users permitted when no explicit assignments exist and demo fallback is enabled
    return user.is_clinical and getattr(settings, "DEMO_FALLBACKS_ENABLED", True)


def require_patient_access(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> str:
    """Validate that the patient exists and that current_user is authorized to access them.
    Raises 404 if patient does not exist, and 403 Forbidden if user lacks permission (prevents IDOR).
    """
    pid = require_patient_id(db, patient_id)
    if not check_patient_authorization(db, current_user, pid):
        raise ForbiddenError(f"User '{current_user.id}' is not authorized to access patient '{patient_id}'.")
    return pid


def require_document_access(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Validate that the document exists and that current_user has access to the owner patient.
    Follows document -> patient -> current_user permission check.
    """
    from app.models.document import Document
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise NotFoundError(f"Document {document_id} not found")

    if not check_patient_authorization(db, current_user, doc.patient_id):
        raise ForbiddenError(f"User '{current_user.id}' is not authorized to access document '{document_id}'.")
    return doc


def get_token_from_credentials(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> Optional[str]:
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials.strip()
    return None


def get_db_session(db: Session = Depends(get_db)) -> Generator[Session, None, None]:
    yield db


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "req_direct")


def resolve_patient_id(patient_id: str) -> str:
    if patient_id in ("demo-patient-001", "demo_patient_001"):
        return "pat_demo_patient_001"
    return patient_id


def require_patient_id(db: Session, patient_id: str) -> str:
    """Resolve aliases and verify the patient exists, else raise 404."""
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
            Patient.is_demo == True,  # noqa: E712
            Patient.deleted_at.is_(None),
        ).first()
        if demo:
            return demo[0] if isinstance(demo, tuple) else demo.id

    raise NotFoundError(f"No patient with id {patient_id}")
