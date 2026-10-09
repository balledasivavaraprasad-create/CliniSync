"""Comprehensive tests for the authentication and session management layer.

Tests:
1. User Registration (success and duplicate rejection)
2. Login with valid credentials (JWT token generation)
3. Login with invalid password (401 Unauthorized)
4. Login with nonexistent user (401 Unauthorized)
5. Protected endpoint access with valid Bearer token
6. Protected endpoint access without token (401 Unauthorized when demo fallback disabled)
7. Protected endpoint access with invalid / malformed token (401 Unauthorized)
8. Protected endpoint access with expired token (401 Unauthorized)
9. Logout / token revocation mechanism
10. Isolated demo fallback behavior check
"""
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.main import app
from app.config import settings
from app.db.database import get_db_context
from app.models.user import User
from app.utils.hashing import hash_password
from app.utils.ids import user_id
from app.utils.tokens import create_access_token

client = TestClient(app)


@pytest.fixture
def auth_user():
    """Ensure a dedicated test user exists in the database."""
    email = "test.dr.auth@clinsync.health"
    with get_db_context() as db:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                id=user_id(),
                email=email,
                full_name="Dr. Auth Test, MD",
                role="doctor",
                specialty="General Medicine",
                hashed_password=hash_password("DoctorSecretPass123!"),
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user


def test_user_registration_success():
    email = f"reg_test_{user_id()}@clinsync.health"
    payload = {
        "email": email,
        "password": "SecurePassword999!",
        "full_name": "Dr. Registered Clinical User",
        "role": "doctor",
        "specialty": "Neurology",
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["email"] == email
    assert data["full_name"] == "Dr. Registered Clinical User"
    assert data["role"] == "doctor"
    assert "password" not in data
    assert "hashed_password" not in data


def test_user_registration_duplicate_email(auth_user):
    payload = {
        "email": auth_user.email,
        "password": "AnyPassword123!",
        "full_name": "Duplicate User",
        "role": "doctor",
        "specialty": "Pediatrics",
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 400
    assert "already exists" in res.json()["error"]["message"]


def test_login_success(auth_user):
    payload = {
        "email": auth_user.email,
        "password": "DoctorSecretPass123!",
    }
    res = client.post("/api/v1/auth/login", json=payload)
    assert res.status_code == 200
    data = res.json()["data"]
    assert "token" in data
    assert data["token"]
    assert data["user"]["email"] == auth_user.email
    assert data["user"]["id"] == auth_user.id


def test_login_invalid_password(auth_user):
    payload = {
        "email": auth_user.email,
        "password": "WrongPassword!",
    }
    res = client.post("/api/v1/auth/login", json=payload)
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


def test_login_nonexistent_user():
    payload = {
        "email": "definitely_does_not_exist@clinsync.health",
        "password": "SomePassword123!",
    }
    res = client.post("/api/v1/auth/login", json=payload)
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


def test_protected_endpoint_with_valid_bearer_token(auth_user):
    token = create_access_token(
        subject=auth_user.id,
        claims={"role": auth_user.role, "email": auth_user.email},
    )
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 200
    user_data = res.json()["data"]
    assert user_data["id"] == auth_user.id
    assert user_data["email"] == auth_user.email


def test_protected_endpoint_without_token_when_demo_disabled(auth_user, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_DEMO_FALLBACK_ENABLED", False)

    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"
    assert "Authentication required" in res.json()["error"]["message"]


def test_protected_endpoint_with_invalid_token(auth_user, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_DEMO_FALLBACK_ENABLED", False)

    headers = {"Authorization": "Bearer invalid.jwt.token"}
    res = client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


def test_protected_endpoint_with_expired_token(auth_user, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_DEMO_FALLBACK_ENABLED", False)

    expired_token = create_access_token(
        subject=auth_user.id,
        expires_delta=timedelta(seconds=-60),
    )
    headers = {"Authorization": f"Bearer {expired_token}"}
    res = client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


def test_logout_and_token_revocation(auth_user, monkeypatch):
    token = create_access_token(
        subject=auth_user.id,
        claims={"role": auth_user.role, "email": auth_user.email},
    )
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Access before logout
    res_before = client.get("/api/v1/auth/me", headers=headers)
    assert res_before.status_code == 200

    # 2. Call logout
    res_logout = client.post("/api/v1/auth/logout", headers=headers)
    assert res_logout.status_code == 200
    assert res_logout.json()["data"]["message"] == "Logged out successfully."

    # 3. Access after logout with demo fallback disabled should be rejected
    monkeypatch.setattr(settings, "AUTH_DEMO_FALLBACK_ENABLED", False)
    res_after = client.get("/api/v1/auth/me", headers=headers)
    assert res_after.status_code == 401
    assert res_after.json()["error"]["code"] == "UNAUTHORIZED"


def test_public_health_endpoints_accessible_without_token(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_DEMO_FALLBACK_ENABLED", False)

    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["data"]["status"] == "healthy"

    res_health_v1 = client.get("/api/v1/health")
    assert res_health_v1.status_code == 200

    res_deep = client.get("/health/deep")
    assert res_deep.status_code in (200, 503)

    res_spec = client.get("/api/v1/specialties")
    assert res_spec.status_code == 200


def test_rate_limiting_on_login():
    """Verify that exceeding rate limits returns 429 Too Many Requests."""
    from app.utils.rate_limit import rate_limiter
    rate_limiter.reset()

    # Attempt rapid repeated logins
    payload = {"email": "ratelimit_probe@clinsync.health", "password": "wrong"}
    responses = [client.post("/api/v1/auth/login", json=payload) for _ in range(16)]

    # 16th request must be rejected with 429
    assert responses[-1].status_code == 429
    assert responses[-1].json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Too many authentication requests" in responses[-1].json()["error"]["message"]

    rate_limiter.reset()

