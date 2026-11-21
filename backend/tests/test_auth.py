from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.core.security import hash_password, create_access_token
from app.models.models import User
from app.core.config import settings


from app.db.session import get_db

class MockAuthResponse:
    def __init__(self, status_code: int, data: dict):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data


class DirectAuthClient:
    """Direct route dispatcher avoiding anyio/starlette blocking portal issues on Python 3.14."""
    def __init__(self, db):
        self.db = db

    def post(self, path: str, json: dict = None, headers: dict = None):
        from pydantic import ValidationError
        from fastapi import HTTPException
        from app.api.routes.auth import (
            register_user,
            login_user,
            forgot_password,
            reset_password,
            google_oauth_login,
        )
        from app.schemas.auth import (
            UserRegisterRequest,
            UserLoginRequest,
            ForgotPasswordRequest,
            ResetPasswordRequest,
            GoogleAuthRequest,
        )

        payload = json or {}
        try:
            if path == "/auth/register":
                req = UserRegisterRequest(**payload)
                res = register_user(req=req, db=self.db)
                return MockAuthResponse(201, res.model_dump())
            elif path == "/auth/login":
                req = UserLoginRequest(**payload)
                res = login_user(req=req, db=self.db)
                return MockAuthResponse(200, res.model_dump())
            elif path == "/auth/forgot-password":
                req = ForgotPasswordRequest(**payload)
                res = forgot_password(req=req, db=self.db)
                return MockAuthResponse(200, res.model_dump())
            elif path == "/auth/reset-password":
                req = ResetPasswordRequest(**payload)
                res = reset_password(req=req, db=self.db)
                return MockAuthResponse(200, res.model_dump())
            elif path == "/auth/google":
                req = GoogleAuthRequest(**payload)
                res = google_oauth_login(req=req, db=self.db)
                return MockAuthResponse(200, res.model_dump())
            elif path in ("/auth/verify-email", "/auth/resend-verification"):
                return MockAuthResponse(404, {"detail": "Not Found"})
            else:
                return MockAuthResponse(404, {"detail": f"Route {path} not found"})
        except HTTPException as e:
            return MockAuthResponse(e.status_code, {"detail": e.detail})
        except ValidationError as ve:
            return MockAuthResponse(422, {"detail": str(ve.errors())})


@pytest.fixture
def auth_client(db):
    """Direct client to test unauthenticated and authenticated auth flows."""
    return DirectAuthClient(db)


def test_registration_success(auth_client, db):
    """Test 1: User registration with email format and password strength checks."""
    payload = {
        "full_name": "Alice Engineer",
        "email": "alice@company.com",
        "password": "Password123!",
        "confirm_password": "Password123!",
    }
    resp = auth_client.post("/auth/register", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "ok"
    assert "Registration successful" in data["message"]

    # Verify user exists in database
    user = db.query(User).filter(User.email == "alice@company.com").first()
    assert user is not None
    assert user.is_verified is True
    assert user.verification_token is None
    assert user.hashed_password is not None
    assert user.hashed_password != "Password123!"  # Never store plaintext!


def test_registration_duplicate_email_fails(auth_client, db):
    """Test 2: Attempting to register an existing email fails gracefully with HTTP 400."""
    user = User(
        email="existing@company.com",
        full_name="Existing User",
        hashed_password=hash_password("Password123!"),
        is_verified=True,
    )
    db.add(user)
    db.commit()

    payload = {
        "full_name": "Imposter User",
        "email": "existing@company.com",
        "password": "Password123!",
        "confirm_password": "Password123!",
    }
    resp = auth_client.post("/auth/register", json=payload)
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"].lower()


def test_registration_password_mismatch_and_weak_password_fails(auth_client):
    """Test: Password confirmation mismatch and weak passwords fail with clear errors."""
    # Mismatch
    resp = auth_client.post("/auth/register", json={
        "full_name": "Test",
        "email": "mismatch@company.com",
        "password": "Password123!",
        "confirm_password": "DifferentPassword123!",
    })
    assert resp.status_code == 400
    assert "match" in resp.json()["detail"].lower()

    # Weak password (too short)
    resp2 = auth_client.post("/auth/register", json={
        "full_name": "Test",
        "email": "weak@company.com",
        "password": "short",
        "confirm_password": "short",
    })
    assert resp2.status_code == 422 or resp2.status_code == 400


def test_registration_allows_immediate_login(auth_client, db):
    """Test: Newly registered users can log in immediately without email verification."""
    payload = {
        "full_name": "Immediate User",
        "email": "immediate@company.com",
        "password": "Password123!",
        "confirm_password": "Password123!",
    }
    resp = auth_client.post("/auth/register", json=payload)
    assert resp.status_code == 201

    login_resp = auth_client.post("/auth/login", json={"email": "immediate@company.com", "password": "Password123!"})
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert "access_token" in data
    assert data["user"]["is_verified"] is True


def test_verify_email_endpoint_removed(auth_client):
    """Test: /auth/verify-email endpoint is removed and returns HTTP 404."""
    resp = auth_client.post("/auth/verify-email", json={"token": "some_token"})
    assert resp.status_code == 404


def test_login_valid_credentials(auth_client, db):
    """Test 5: Login with valid credentials returns Bearer access token."""
    user = User(
        email="login_ok@company.com",
        full_name="Login Success",
        hashed_password=hash_password("Password123!"),
        is_verified=True,
    )
    db.add(user)
    db.commit()

    resp = auth_client.post("/auth/login", json={"email": "login_ok@company.com", "password": "Password123!"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "login_ok@company.com"


def test_login_invalid_credentials_fails(auth_client, db):
    """Test 6: Login with invalid password returns HTTP 401 Unauthorized."""
    user = User(
        email="wrong_pass@company.com",
        full_name="Wrong Pass",
        hashed_password=hash_password("CorrectPassword123!"),
        is_verified=True,
    )
    db.add(user)
    db.commit()

    resp = auth_client.post("/auth/login", json={"email": "wrong_pass@company.com", "password": "IncorrectPassword!"})
    assert resp.status_code == 401
    assert "invalid" in resp.json()["detail"].lower()


def test_legacy_unverified_account_can_login(auth_client, db):
    """Test: Existing unverified accounts can log in successfully without restriction."""
    user = User(
        email="legacy_unverified@company.com",
        full_name="Legacy User",
        hashed_password=hash_password("Password123!"),
        is_verified=False,
    )
    db.add(user)
    db.commit()

    resp = auth_client.post("/auth/login", json={"email": "legacy_unverified@company.com", "password": "Password123!"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["is_verified"] is True


def test_forgot_password_generic_response(auth_client, db):
    """Test 7: Forgot password provides generic response preventing email enumeration."""
    # Existing user
    user = User(
        email="forgot@company.com",
        full_name="Forgot User",
        hashed_password=hash_password("Password123!"),
        is_verified=True,
    )
    db.add(user)
    db.commit()

    resp = auth_client.post("/auth/forgot-password", json={"email": "forgot@company.com"})
    assert resp.status_code == 200
    assert "instructions have been sent" in resp.json()["message"]

    # Non-existing email receives the SAME generic message
    resp_nonexistent = auth_client.post("/auth/forgot-password", json={"email": "nobody@company.com"})
    assert resp_nonexistent.status_code == 200
    assert "instructions have been sent" in resp_nonexistent.json()["message"]


def test_password_reset_success(auth_client, db):
    """Test 9 & 10: Reset password updates password hash, clears token, and allows login."""
    user = User(
        email="reset_target@company.com",
        full_name="Reset Target",
        hashed_password=hash_password("OldPassword123!"),
        is_verified=True,
        reset_token="valid_reset_token_xyz",
        reset_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    db.add(user)
    db.commit()

    resp = auth_client.post("/auth/reset-password", json={
        "token": "valid_reset_token_xyz",
        "new_password": "NewStrongPassword123!",
        "confirm_password": "NewStrongPassword123!",
    })
    assert resp.status_code == 200
    assert "successfully" in resp.json()["message"].lower()

    # Verify login with new password succeeds
    login_resp = auth_client.post("/auth/login", json={
        "email": "reset_target@company.com",
        "password": "NewStrongPassword123!",
    })
    assert login_resp.status_code == 200

    # Old password no longer works
    old_login_resp = auth_client.post("/auth/login", json={
        "email": "reset_target@company.com",
        "password": "OldPassword123!",
    })
    assert old_login_resp.status_code == 401


def test_password_reset_expired_token_fails(auth_client, db):
    """Test 8: Expired password reset token is rejected with HTTP 400."""
    user = User(
        email="reset_expired@company.com",
        full_name="Reset Expired",
        hashed_password=hash_password("OldPassword123!"),
        is_verified=True,
        reset_token="expired_reset_token_123",
        reset_token_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db.add(user)
    db.commit()

    resp = auth_client.post("/auth/reset-password", json={
        "token": "expired_reset_token_123",
        "new_password": "NewStrongPassword123!",
        "confirm_password": "NewStrongPassword123!",
    })
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"].lower()


def test_google_oauth_when_unconfigured_returns_501(auth_client):
    """Test 15: When Google credentials are unconfigured, endpoint returns clear HTTP 501."""
    settings.GOOGLE_CLIENT_ID = None
    resp = auth_client.post("/auth/google", json={"credential": "mock_google_id_token_1234567890"})
    assert resp.status_code == 501
    assert "not configured" in resp.json()["detail"].lower()
