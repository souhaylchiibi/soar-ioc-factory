"""Dashboard endpoints: audit trail, workflow summary, system health.

Everything here reads the local database — no fabricated figures.
n8n execution counts are mirrored from our own audit trail (actor=workflow-*),
so the dashboard never depends on n8n being reachable.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import check_database, get_db
from app.models.ioc import AuditLog, Ioc, IntelSource

router = APIRouter(tags=["dashboard"])


# ------------------------------------------------------------- audit logs ---
@router.get("/audit")
def list_audit(
    db: Session = Depends(get_db),
    action: Optional[str] = Query(None, max_length=40),
    actor: Optional[str] = Query(None, max_length=64),
    success: Optional[bool] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Paginated audit trail (append-only table)."""
    clauses = []
    if action:
        clauses.append(AuditLog.action == action)
    if actor:
        clauses.append(AuditLog.actor.like(f"{actor}%"))
    if success is not None:
        clauses.append(AuditLog.success.is_(success))

    total = db.execute(select(func.count(AuditLog.id)).where(*clauses)).scalar() or 0
    rows = db.execute(
        select(AuditLog)
        .where(*clauses)
        .order_by(AuditLog.id.desc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()

    return {
        "total": int(total),
        "offset": offset,
        "limit": limit,
        "entries": [
            {
                "id": r.id,
                "occurred_at": r.occurred_at.isoformat(),
                "actor": r.actor,
                "action": r.action,
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "success": r.success,
                "error": r.error,
                "detail": r.detail,
            }
            for r in rows
        ],
    }


@router.get("/audit/actions", tags=["audit"])
def audit_actions(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Distinct actions + counts — powers filter dropdowns."""
    rows = db.execute(
        select(AuditLog.action, func.count(AuditLog.id)).group_by(AuditLog.action)
    ).all()
    return {"actions": [{"action": a, "count": int(c)} for a, c in sorted(rows)]}


# ---------------------------------------------------- workflow summary ------
@router.get("/workflows/summary")
def workflows_summary(
    db: Session = Depends(get_db),
    days: int = Query(7, ge=1, le=90),
) -> dict[str, Any]:
    """Aggregated automation activity derived from the audit trail.

    The 8 workflows are identified by the `workflow-N` actor prefix written
    by the API during their executions.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(
        select(
            AuditLog.actor,
            AuditLog.action,
            func.count(AuditLog.id),
            func.count(AuditLog.id).filter(AuditLog.success.is_(True)),
            func.count(AuditLog.id).filter(AuditLog.success.is_(False)),
            func.max(AuditLog.occurred_at),
        )
        .where(AuditLog.occurred_at >= since)
        .where(AuditLog.actor.like("workflow-%"))
        .group_by(AuditLog.actor, AuditLog.action)
    ).all()

    by_workflow: dict[str, dict[str, Any]] = {}
    for actor, action, total, ok, ko, last in rows:
        wf = actor.split("/")[0]
        entry = by_workflow.setdefault(wf, {
            "workflow": wf, "operations": 0, "success": 0, "failed": 0,
            "actions": [], "last_run_at": None,
        })
        entry["operations"] += int(total)
        entry["success"] += int(ok)
        entry["failed"] += int(ko)
        entry["actions"].append({"action": action, "count": int(total)})
        if entry["last_run_at"] is None or last > entry["last_run_at"]:
            entry["last_run_at"] = last

    result = []
    for entry in sorted(by_workflow.values(), key=lambda e: e["workflow"]):
        entry["last_run_at"] = entry["last_run_at"].isoformat() if entry["last_run_at"] else None
        entry["actions"].sort(key=lambda a: -a["count"])
        result.append(entry)

    return {"window_days": days, "workflows": result, "count": len(result)}


# ---------------------------------------------------------- system health ---
@router.get("/system/health")
def system_health(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Health of the whole stack as observable from the API (read-only)."""
    checks: dict[str, Any] = {}

    # 1. Database
    ok, detail = check_database()
    checks["database"] = {"status": "ok" if ok else "error", "detail": detail}

    # 2. Schema (alembic head applied?)
    try:
        version = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
        checks["migrations"] = {"status": "ok", "head": version}
    except Exception as exc:
        checks["migrations"] = {"status": "error", "detail": str(exc)[:200]}

    # 3. Audit trail writability probe (append-only trigger intact?)
    try:
        triggers = db.execute(text(
            "SELECT count(*) FROM pg_trigger WHERE tgname='trg_audit_immutable' AND NOT tgisinternal"
        )).scalar()
        checks["audit_append_only"] = {
            "status": "ok" if int(triggers or 0) == 1 else "warning",
            "triggers": int(triggers or 0),
        }
    except Exception as exc:
        checks["audit_append_only"] = {"status": "error", "detail": str(exc)[:200]}

    # 4. Intelligence sources (table may not exist on a fresh DB)
    try:
        src_total, src_enabled, src_key_required = db.execute(
            select(
                func.count(IntelSource.id),
                func.count(IntelSource.id).filter(IntelSource.enabled.is_(True)),
                func.count(IntelSource.id).filter(IntelSource.requires_api_key.is_(True)),
            )
        ).one()
        checks["intel_sources"] = {
            "status": "ok" if int(src_enabled) > 0 else "warning",
            "total": int(src_total), "enabled": int(src_enabled),
            "require_key": int(src_key_required),
        }
    except Exception as exc:
        checks["intel_sources"] = {"status": "error", "detail": str(exc)[:200]}

    # 5. API keys present (lengths only — values never leave the server)
    checks["api_keys"] = {
        "OTX": bool(settings.otx_api_key),
        "AbuseIPDB": bool(settings.abuseipdb_api_key),
        "abuse_ch": bool(settings.abusech_auth_key),
        "MISP": bool(settings.misp_key),
    }

    # 6. Recent activity
    last_audit = db.execute(select(func.max(AuditLog.occurred_at))).scalar()
    checks["last_activity_at"] = last_audit.isoformat() if last_audit else None
    stale = True
    if last_audit:
        stale = (datetime.now(timezone.utc) - last_audit) > timedelta(hours=24)
    checks["activity_freshness"] = {"status": "stale" if stale else "ok"}

    # 7. Inventory snapshot (fresh DB => empty, never an exception)
    try:
        counts = db.execute(
            select(Ioc.status, func.count(Ioc.id)).group_by(Ioc.status)
        ).all()
        checks["inventory"] = {k.value if hasattr(k, "value") else str(k): int(v)
                               for k, v in counts}
    except Exception as exc:
        checks["inventory"] = {"error": str(exc)[:200]}

    degraded = [name for name, c in checks.items()
                if isinstance(c, dict) and c.get("status") in ("error", "warning")]
    overall = "degraded" if degraded else "healthy"

    return {
        "status": overall,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "app": {"name": settings.app_name, "env": settings.app_env},
        "checks": checks,
        "degraded_checks": degraded,
    }
