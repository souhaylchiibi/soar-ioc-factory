"""Test fixtures — Phase 3 integration tests run against a REAL PostgreSQL.

A dedicated database (`soar_ioc_test`) is created and migrated with Alembic
once per session; tables are truncated between tests. This exercises the
actual schema (constraints, enums, trigger), not a SQLite stand-in.
"""
import os
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]  # .../backend (contains alembic.ini)
TEST_DB = os.environ.get("TEST_DATABASE_NAME", "soar_ioc_test")


def _admin_url() -> str:
    """URL on the `soar` maintenance database (to CREATE DATABASE)."""
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    user = os.environ.get("POSTGRES_USER", "soar")
    password = os.environ.get("POSTGRES_PASSWORD", "")
    port = os.environ.get("POSTGRES_PORT", "5432")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/postgres"


def _test_url() -> str:
    return _admin_url().rsplit("/", 1)[0] + f"/{TEST_DB}"


def _ensure_test_db() -> str:
    url = _test_url()
    try:
        engine = create_engine(_admin_url(), isolation_level="AUTOCOMMIT")
        with engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db"), {"db": TEST_DB}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{TEST_DB}"'))
        engine.dispose()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"PostgreSQL indisponible pour les tests: {exc}")

    # Migrate the test DB with the real Alembic migrations (same schema as prod).
    env = dict(os.environ, DATABASE_URL=url, PYTHONPATH=str(BACKEND_DIR))
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
        capture_output=True,
        timeout=120,
    )
    return url


@pytest.fixture(scope="session")
def test_db_url() -> str:
    return _ensure_test_db()


@pytest.fixture()
def db(test_db_url: str) -> Generator[Session, None, None]:
    """Transactional session; every table is truncated between tests."""
    engine = create_engine(test_db_url, pool_pre_ping=True, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()

    tables = (
        "detections, publications, score_history, enrichments, lifecycle_events, "
        "ioc_sources, iocs, intel_sources, users, reports, scoring_policies, audit_logs"
    )
    session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    session.commit()

    yield session

    session.rollback()
    session.close()
    engine.dispose()
