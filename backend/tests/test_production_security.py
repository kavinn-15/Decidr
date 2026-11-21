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
