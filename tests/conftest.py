import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, get_db
from app.main import app
import app.services.job_service as job_service_module


@pytest.fixture(scope="session", autouse=True)
def configure_test_environment(tmp_path_factory):
    """Set up temporary directories for testing storage and database."""
    temp_dir = tmp_path_factory.mktemp("test_app_data")
    temp_storage = temp_dir / "storage"
    temp_storage.mkdir(parents=True, exist_ok=True)

    # Point settings to temp storage
    settings.STORAGE_DIR = str(temp_storage)

    test_db_path = temp_dir / "test.db"
    settings.DATABASE_URL = f"sqlite:///{test_db_path.as_posix()}"

    # Create test engine and sessionmaker
    test_engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        future=True,
    )
    TestingSessionLocal = sessionmaker(
        bind=test_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

    # Create tables
    Base.metadata.create_all(bind=test_engine)

    # Monkeypatch SessionLocal in job_service module so background tasks use test db
    original_session_local = job_service_module.SessionLocal
    job_service_module.SessionLocal = TestingSessionLocal

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    yield

    # Teardown
    app.dependency_overrides.clear()
    job_service_module.SessionLocal = original_session_local


@pytest.fixture
def client():
    """FastAPI TestClient fixture that executes background tasks synchronously."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    """Direct database session fixture for inspecting test database state."""
    test_engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        future=True,
    )
    Session = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
