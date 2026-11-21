import sqlite3
from typing import Generator
from sqlalchemy import create_engine, event, text
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


connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(engine_instance: Engine | None = None) -> None:
    """Initialize database tables."""
    eng = engine_instance or engine
    Base.metadata.create_all(bind=eng)
    with eng.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE premises ADD COLUMN last_supported_at DATETIME;"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE premises ADD COLUMN confidence FLOAT;"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN estimate_points FLOAT;"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE meetings ADD COLUMN owner_id INTEGER;"))
            conn.commit()
        except Exception:
            pass

    # Ensure default demo user exists for seamless demo experience and backward compatibility
    with Session(bind=eng) as session:
        try:
            from app.models.models import User
            from app.core.security import hash_password
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
                session.commit()
        except Exception:
            session.rollback()

