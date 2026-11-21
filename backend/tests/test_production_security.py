import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import Settings, settings, DEV_JWT_SECRET
from app.core.security import hash_password
from app.db.session import get_engine_args
from app.models.models import User
from app.api.deps import require_admin_user
from app.services.storage import upload_transcript_file
from app.main import reset_demo_database


def test_production_jwt_secret_validation():
    """Validates that production environment requires a 32+ character non-default JWT secret."""
    with pytest.raises(ValueError, match="at least 32 characters"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="short-secret",
            DEMO_MODE=False,
            DATABASE_URL="postgresql://user:pass@host:5432/db",
        )

    with pytest.raises(ValueError, match="cannot use DEV_JWT_SECRET"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY=DEV_JWT_SECRET,
            DEMO_MODE=False,
            DATABASE_URL="postgresql://user:pass@host:5432/db",
        )


def test_production_demo_mode_validation():
    """Validates that DEMO_MODE must be false in production."""
    with pytest.raises(ValueError, match="DEMO_MODE must be set to false in production"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="a" * 32,
            DEMO_MODE=True,
            DATABASE_URL="postgresql://user:pass@host:5432/db",
        )


def test_production_sqlite_rejection():
    """Validates that SQLite is rejected in production."""
    with pytest.raises(ValueError, match="Production requires a PostgreSQL database URL"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="a" * 32,
            DEMO_MODE=False,
            DATABASE_URL="sqlite:///./prod.db",
        )


def test_database_url_normalization():
    """Validates PostgreSQL driver normalization for Supabase URLs."""
    s1 = Settings(DATABASE_URL="postgres://postgres.abc:pass@aws-0-us-west-1.pooler.supabase.com:6543/postgres")
    assert s1.DATABASE_URL.startswith("postgresql+psycopg2://")

    s2 = Settings(DATABASE_URL="postgresql://postgres.abc:pass@aws-0-us-west-1.pooler.supabase.com:6543/postgres")
    assert s2.DATABASE_URL.startswith("postgresql+psycopg2://")


def test_cors_origins_parsing():
    """Validates comma-separated CORS_ORIGINS string parsing."""
    s = Settings(CORS_ORIGINS="https://decidr.vercel.app, http://localhost:3000")
    assert s.CORS_ORIGINS == ["https://decidr.vercel.app", "http://localhost:3000"]


def test_cors_origins_includes_production_frontend():
    """Validates that default CORS_ORIGINS permits the Vercel production frontend."""
    s = Settings()
    assert "https://decidr-pi.vercel.app" in s.CORS_ORIGINS
    assert "https://decidr.vercel.app" in s.CORS_ORIGINS


def test_postgres_engine_args_ssl_and_pool():
    """Validates connection pool and SSL parameters for remote PostgreSQL hosts."""
    url = "postgresql+psycopg2://user:pass@aws-0-us-west-1.pooler.supabase.com:6543/postgres"
    kwargs, connect_args = get_engine_args(url)
    assert kwargs.get("pool_pre_ping") is True
    assert kwargs.get("pool_size") == 5
    assert connect_args.get("sslmode") == "require"


def test_storage_fallback_without_credentials():
    """Validates that storage falls back gracefully when Supabase Storage is unconfigured."""
    ref = upload_transcript_file(
        content_bytes=b"WEBVTT\n00:00.000 --> 00:05.000\nSpeaker: Hello",
        original_filename="meeting.vtt",
        project="TestProject",
    )
    assert ref == "meeting.vtt"


def test_admin_routes_reject_non_admin():
    """Validates that non-admin users cannot satisfy require_admin_user."""
    member = User(
        email="member@test.com",
        full_name="Standard Member",
        hashed_password=hash_password("StrongPass123!"),
        is_verified=True,
        is_active=True,
        role="member",
    )
    with pytest.raises(HTTPException) as exc_info:
        require_admin_user(current_user=member)
    assert exc_info.value.status_code == 403
    assert "Administrative privileges required" in exc_info.value.detail

    admin = User(
        email="admin@test.com",
        full_name="Admin User",
        hashed_password=hash_password("StrongPass123!"),
        is_verified=True,
        is_active=True,
        role="admin",
    )
    validated = require_admin_user(current_user=admin)
    assert validated.email == "admin@test.com"


def test_demo_reset_disabled_in_production(monkeypatch):
    """Validates that reset_demo_database is completely forbidden in production even for admin users."""
    admin = User(
        email="admin@test.com",
        full_name="Admin User",
        hashed_password=hash_password("StrongPass123!"),
        is_verified=True,
        is_active=True,
        role="admin",
    )

    # Simulate production environment
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "DEMO_MODE", False)

    with pytest.raises(HTTPException) as exc_info:
        reset_demo_database(admin_user=admin)
    assert exc_info.value.status_code == 403
    assert "disabled in production" in exc_info.value.detail


def test_demo_user_seeded_and_can_login():
    """Validates that init_db() ensures the demo user exists and can authenticate."""
    from app.db.session import SessionLocal, init_db
    from app.api.routes.auth import login_user
    from app.schemas.auth import UserLoginRequest

    init_db()

    with SessionLocal() as db:
        demo = db.query(User).filter(User.email == "demo@decidr.ai").first()
        assert demo is not None
        assert demo.is_verified is True
        assert demo.is_active is True
        assert demo.role == "admin"

        # Test valid demo login
        req = UserLoginRequest(email="demo@decidr.ai", password="DecidrDemo2026!")
        token_resp = login_user(req=req, db=db)
        assert token_resp.access_token is not None
        assert token_resp.token_type == "bearer"
        assert token_resp.user.email == "demo@decidr.ai"


def test_new_user_registration_and_login_flow():
    """Validates that newly registered users persist and can immediately log in."""
    import uuid
    from app.db.session import SessionLocal
    from app.api.routes.auth import register_user, login_user
    from app.schemas.auth import UserRegisterRequest, UserLoginRequest

    test_email = f"user_{uuid.uuid4().hex[:8]}@decidr.ai"
    test_password = "SecurePassword2026!"

    with SessionLocal() as db:
        reg_req = UserRegisterRequest(
            full_name="New Test User",
            email=test_email,
            password=test_password,
            confirm_password=test_password,
        )
        reg_resp = register_user(req=reg_req, db=db)
        assert reg_resp.status == "ok"

        # Verify persisted in database
        saved_user = db.query(User).filter(User.email == test_email).first()
        assert saved_user is not None
        assert saved_user.is_active is True

        # Log in with newly registered credentials
        login_req = UserLoginRequest(email=test_email, password=test_password)
        login_resp = login_user(req=login_req, db=db)
        assert login_resp.access_token is not None
        assert login_resp.user.email == test_email


def test_invalid_credentials_return_401():
    """Validates that invalid passwords or non-existent emails return HTTP 401."""
    from app.db.session import SessionLocal
    from app.api.routes.auth import login_user
    from app.schemas.auth import UserLoginRequest

    with SessionLocal() as db:
        # Non-existent user
        with pytest.raises(HTTPException) as exc1:
            login_user(
                req=UserLoginRequest(email="nonexistent@decidr.ai", password="SomePassword123!"),
                db=db,
            )
        assert exc1.value.status_code == 401
        assert "Invalid email or password." in exc1.value.detail

        # Existing demo user with wrong password
        with pytest.raises(HTTPException) as exc2:
            login_user(
                req=UserLoginRequest(email="demo@decidr.ai", password="WrongPassword123!"),
                db=db,
            )
        assert exc2.value.status_code == 401
        assert "Invalid email or password." in exc2.value.detail


def test_verified_email_flow_when_email_service_is_active(monkeypatch):
    """Validates that when email service is active, unverified users get 403 until verified."""
    import uuid
    from app.db.session import SessionLocal
    from app.api.routes.auth import register_user, login_user, verify_email
    from app.schemas.auth import UserRegisterRequest, UserLoginRequest, VerifyEmailRequest
    import app.api.routes.auth as auth_module

    # Mock email delivery as active
    monkeypatch.setattr(auth_module, "is_email_configured", lambda: True)
    # Mock dispatch so no real network call is made
    monkeypatch.setattr(auth_module, "send_verification_email", lambda email, name, token: (True, None))

    test_email = f"verified_flow_{uuid.uuid4().hex[:8]}@decidr.ai"
    test_password = "SecurePassword2026!"

    with SessionLocal() as db:
        reg_req = UserRegisterRequest(
            full_name="Verified Flow User",
            email=test_email,
            password=test_password,
            confirm_password=test_password,
        )
        reg_resp = register_user(req=reg_req, db=db)
        assert reg_resp.email_sent is True

        # Check DB: is_verified must be False while email service is active
        saved = db.query(User).filter(User.email == test_email).first()
        assert saved.is_verified is False
        token = saved.verification_token
        assert token is not None

        # Trying to log in before verification must raise 403 Forbidden
        with pytest.raises(HTTPException) as exc_login:
            login_user(req=UserLoginRequest(email=test_email, password=test_password), db=db)
        assert exc_login.value.status_code == 403
        assert "verify your email" in exc_login.value.detail

        # Complete email verification
        ver_resp = verify_email(req=VerifyEmailRequest(token=token), db=db)
        assert ver_resp.access_token is not None
        assert ver_resp.user.is_verified is True

        # Now login must succeed with 200
        login_resp = login_user(req=UserLoginRequest(email=test_email, password=test_password), db=db)
        assert login_resp.access_token is not None
        assert login_resp.user.email == test_email


