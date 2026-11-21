import pytest
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
import sqlite3

from app.db.session import Base, get_db
from app.models.models import *  # noqa: F401, F403
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(eng, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        if isinstance(dbapi_connection, sqlite3.Connection):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.close()

    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture
def db(engine: Engine) -> Generator[Session, None, None]:
    connection = engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    if trans.is_active:
        trans.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def default_auth_dependency_override(db: Session):
    from app.models.models import User
    from app.core.security import hash_password
    from app.api.deps import get_current_user

    demo_user = db.query(User).filter(User.email == "demo@decidr.ai").first()
    if not demo_user:
        demo_user = User(
            email="demo@decidr.ai",
            full_name="Decidr Demo Admin",
            hashed_password=hash_password("DecidrDemo2026!"),
            is_verified=True,
            is_active=True,
            role="admin",
        )
        db.add(demo_user)
        db.commit()

    app.dependency_overrides[get_current_user] = lambda: demo_user
    yield demo_user
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
