from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from jose import jwt, JWTError

from app.config import settings

# In-memory revocation set for logged-out tokens (or token jti/hashes)
_REVOKED_TOKENS: set[str] = set()


def create_access_token(
    subject: str,
    claims: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT access token."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode: Dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if claims:
        to_encode.update(claims)

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token. Raises JWTError if invalid or expired."""
    if is_token_revoked(token):
        raise JWTError("Token has been revoked")

    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    return payload


def revoke_token(token: str) -> None:
    """Add token to revocation set."""
    _REVOKED_TOKENS.add(token)


def is_token_revoked(token: str) -> bool:
    """Check if token was revoked."""
    return token in _REVOKED_TOKENS
