import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_request_id
from app.api.errors import BadRequestError, NotFoundError, UnauthorizedError
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UserResponse,
)
from app.schemas.common import SuccessResponse, Meta
from app.utils.hashing import hash_password, verify_password
from app.utils.ids import user_id

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        specialty=user.specialty,
        is_active=user.is_active,
        avatar_url=user.avatar_url,
    )


@router.post("/login", response_model=SuccessResponse[LoginResponse])
def login(
    req: LoginRequest,
    db: Session = Depends(get_db_session),
    req_id: str = Depends(get_request_id),
):
    """Authenticate a clinician or doctor with email and password against the database."""
    email_clean = req.email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()

    if not user:
        # Check case-insensitive match as fallback
        user = db.query(User).filter(User.email.ilike(email_clean)).first()

    if not user or not verify_password(req.password, user.hashed_password):
        raise UnauthorizedError("Invalid email or password.")

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This clinical user account is inactive.",
        )

    # Issue a secure session token
    token = f"cls_{secrets.token_urlsafe(32)}"

    return SuccessResponse(
        data=LoginResponse(
            token=token,
            user=_user_to_response(user),
        ),
        meta=Meta(request_id=req_id, source="db"),
    )


@router.post("/register", response_model=SuccessResponse[UserResponse])
def register(
    req: RegisterRequest,
    db: Session = Depends(get_db_session),
    req_id: str = Depends(get_request_id),
):
    """Register a new clinician or doctor account."""
    email_clean = req.email.strip().lower()
    existing = db.query(User).filter(User.email == email_clean).first()
    if existing:
        raise BadRequestError(f"An account with email '{email_clean}' already exists.")

    new_user = User(
        id=user_id(),
        email=email_clean,
        full_name=req.full_name.strip(),
        role=req.role.strip() or "doctor",
        specialty=req.specialty.strip() or "General Medicine",
        hashed_password=hash_password(req.password),
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return SuccessResponse(
        data=_user_to_response(new_user),
        meta=Meta(request_id=req_id, source="db"),
    )


@router.get("/me", response_model=SuccessResponse[UserResponse])
def get_me(
    db: Session = Depends(get_db_session),
    req_id: str = Depends(get_request_id),
):
    """Return the primary active clinician profile."""
    user = db.query(User).filter(User.is_active == True).first()
    if not user:
        raise NotFoundError("No active clinician account found.")

    return SuccessResponse(
        data=_user_to_response(user),
        meta=Meta(request_id=req_id, source="db"),
    )


@router.post("/logout")
def logout(req_id: str = Depends(get_request_id)):
    """Clear clinician session."""
    return SuccessResponse(
        data={"message": "Logged out successfully."},
        meta=Meta(request_id=req_id, source="system"),
    )
