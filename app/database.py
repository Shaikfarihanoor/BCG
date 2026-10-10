from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

from pathlib import Path

# SQLite requires check_same_thread=False when used across FastAPI threads/background tasks
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    if settings.DATABASE_URL.startswith("sqlite:///"):
        db_file = settings.DATABASE_URL.replace("sqlite:///", "")
        if db_file and db_file != ":memory:":
            Path(db_file).resolve().parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DEBUG,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""
    pass


def get_db() -> Generator[Session, None, None]:
    """Dependency that yields a database session and guarantees closure."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables registered with Base metadata."""
    Base.metadata.create_all(bind=engine)
