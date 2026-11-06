"""SQLAlchemy engine / session management."""
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Marker for all ORM models."""


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a transactional session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database() -> tuple[bool, str]:
    """Cheap connectivity probe used by /health and /ready."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as exc:  # pragma: no cover - failure path
        return False, str(exc)
