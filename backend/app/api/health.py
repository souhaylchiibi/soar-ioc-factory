"""Health and readiness probes."""
from fastapi import APIRouter, Response, status

from app.core.db import check_database

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness: process is up. Never touches dependencies."""
    return {"status": "ok"}


@router.get("/ready")
def ready(response: Response) -> dict:
    """Readiness: dependencies reachable. 503 if PostgreSQL is down."""
    db_ok, detail = check_database()
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if db_ok else "degraded", "database": {"status": "ok" if db_ok else "error", "detail": detail}}
