import sqlite3
from typing import Generator
from urllib.parse import urlparse
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import settings

Base = declarative_base()


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable SQLite foreign key constraints, WAL journal mode, and busy timeout."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.close()


def get_engine_args(db_url: str) -> tuple[dict, dict]:
    """
    Returns (engine_kwargs, connect_args) customized for SQLite or PostgreSQL.
    Configures connection pooling and SSL mode safely for Supabase.
    """
    engine_kwargs = {"echo": False}
    connect_args = {}

    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    else:
        # PostgreSQL (Supabase / Render)
        engine_kwargs["pool_pre_ping"] = True
        engine_kwargs["pool_size"] = 5
        engine_kwargs["max_overflow"] = 10
        engine_kwargs["pool_recycle"] = 300

        # Handle Supabase SSL requirements
        parsed = urlparse(db_url)
        is_local = parsed.hostname in ("localhost", "127.0.0.1", None)
        if not is_local and "sslmode" not in db_url:
            connect_args["sslmode"] = "require"

    engine_kwargs["connect_args"] = connect_args
    return engine_kwargs, connect_args


_engine_kwargs, _ = get_engine_args(settings.DATABASE_URL)
engine = create_engine(settings.DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(engine_instance: Engine | None = None) -> None:
    """Initialize database tables and seed initial demo admin if needed."""
    eng = engine_instance or engine
    Base.metadata.create_all(bind=eng)

    # Seed or verify demo user
    with Session(bind=eng) as session:
        try:
            from app.models.models import User
            from app.core.security import hash_password
            # Automatically verify any existing unverified accounts
            session.query(User).filter(User.is_verified == False).update({"is_verified": True})
            demo_user = session.query(User).filter(User.email == "demo@decidr.ai").first()
            if not demo_user:
                demo_user = User(
                    email="demo@decidr.ai",
                    full_name="Decidr Demo Admin",
                    hashed_password=hash_password("DecidrDemo2026!"),
                    is_verified=True,
                    is_active=True,
                    role="admin",
                )
                session.add(demo_user)
            else:
                demo_user.is_verified = True
                demo_user.is_active = True
            session.commit()
        except Exception:
            session.rollback()
