"""Live status of every integration, as observable from the API.

Each probe returns one of:
  connected       — reachable/working right now (checked, not assumed)
  not_configured  — credentials/URL absent: nothing was attempted
  no_data         — configured/mounted but nothing to read yet
  unreachable     — configured but the probe failed (error kept verbatim)
  degraded        — partially working (e.g. some collectors failing)

Results are cached briefly so the dashboard can poll without hammering
remote services.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Optional

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import check_database
from app.models.ioc import AuditLog, IntelSource

_CACHE_TTL_S = 30.0
_cache: dict[str, Any] = {"at": 0.0, "value": None}
_lock = Lock()

# Sources whose collector needs a key, and which setting provides it.
SOURCE_KEYS = {
    "alienvault_otx": "otx_api_key",
    "urlhaus": "abusech_auth_key",
    "threatfox": "abusech_auth_key",
    "malwarebazaar": "abusech_auth_key",
}


def _iso(ts: Optional[datetime]) -> Optional[str]:
    return ts.isoformat() if ts else None


def _last_audit(db: Session, action: str, actor_like: Optional[str] = None) -> Optional[AuditLog]:
    stmt = select(AuditLog).where(AuditLog.action == action)
    if actor_like:
        stmt = stmt.where(AuditLog.actor.like(actor_like))
    return db.execute(stmt.order_by(AuditLog.id.desc()).limit(1)).scalar_one_or_none()


def _sensor(db: Session, name: str, rel_path: str) -> dict[str, Any]:
    path = Path(settings.sensor_root) / rel_path
    last = _last_audit(db, "OBSERVE", f"%/{name}")
    out: dict[str, Any] = {
        "name": name, "kind": "sensor", "file": str(path),
        "last_ingest_at": _iso(last.occurred_at) if last else None,
        "last_ingest": (last.detail if last else None),
    }
    if not path.exists():
        out.update(status="no_data",
                   detail="aucun fichier d'alertes monté : capteur arrêté ou profil Docker inactif")
        return out
    stat = path.stat()
    out.update(
        status="connected" if stat.st_size > 0 else "no_data",
        detail="fichier d'alertes présent" if stat.st_size > 0 else "fichier d'alertes vide",
        file_size=stat.st_size,
        file_modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    )
    return out


def _misp() -> dict[str, Any]:
    out: dict[str, Any] = {"name": "misp", "kind": "publication"}
    if not settings.misp_url or not settings.misp_key:
        out.update(status="not_configured", detail="MISP_URL / MISP_KEY absents du .env")
        return out
    from app.integrations.misp import MispClient, MispError

    try:
        version = MispClient(base_url=settings.misp_url, api_key=settings.misp_key,
                             verify_tls=settings.misp_verify_cert, timeout=4.0).health()
        out.update(status="connected", detail=f"MISP {version}", url=settings.misp_url)
    except (MispError, httpx.HTTPError, TypeError) as exc:
        out.update(status="unreachable", detail=str(exc)[:200], url=settings.misp_url)
    return out


def _n8n(db: Session) -> dict[str, Any]:
    out: dict[str, Any] = {"name": "n8n", "kind": "automation", "url": settings.n8n_url}
    last = db.execute(
        select(func.max(AuditLog.occurred_at)).where(AuditLog.actor.like("workflow-%"))
    ).scalar()
    out["last_workflow_activity_at"] = _iso(last)
    try:
        r = httpx.get(f"{settings.n8n_url.rstrip('/')}/healthz", timeout=2.0)
        if r.status_code == 200:
            out.update(status="connected", detail="n8n /healthz OK")
        else:
            out.update(status="unreachable", detail=f"HTTP {r.status_code}")
    except httpx.HTTPError as exc:
        out.update(status="unreachable",
                   detail=f"n8n injoignable ({type(exc).__name__}) — profil n8n démarré ?")
    return out


def collection_history(db: Session) -> dict[str, dict[str, Any]]:
    """Last successful / failed collection per source, from the audit trail.

    The audit trail is the proof of every run (it also covers runs made
    before intel_sources.last_* were maintained).
    """
    out: dict[str, dict[str, Any]] = {}
    rows = db.execute(
        select(AuditLog.entity_id, AuditLog.success, func.max(AuditLog.id))
        .where(AuditLog.action == "COLLECT", AuditLog.entity_type == "source")
        .group_by(AuditLog.entity_id, AuditLog.success)
    ).all()
    for name, success, last_id in rows:
        entry = db.get(AuditLog, last_id)
        h = out.setdefault(name, {"last_success_at": None, "last_error_at": None, "last_error": None})
        if success:
            h["last_success_at"] = entry.occurred_at
        else:
            h["last_error_at"] = entry.occurred_at
            h["last_error"] = entry.error
    return out


def _latest(a: Optional[datetime], b: Optional[datetime]) -> Optional[datetime]:
    return max((x for x in (a, b) if x is not None), default=None)


def source_state(db: Session) -> dict[str, dict[str, Any]]:
    """Per-source connection state used by /integrations/status and /sources."""
    history = collection_history(db)
    states: dict[str, dict[str, Any]] = {}
    for s in db.execute(select(IntelSource).order_by(IntelSource.name)).scalars():
        h = history.get(s.name, {})
        last_ok = _latest(s.last_success_at, h.get("last_success_at"))
        last_err = _latest(s.last_error_at, h.get("last_error_at"))
        err_msg = s.last_error if s.last_error_at and s.last_error_at == last_err else h.get("last_error")
        key_setting = SOURCE_KEYS.get(s.name)
        key_ok = bool(getattr(settings, key_setting)) if key_setting else None
        failing = bool(last_err and (not last_ok or last_err > last_ok))
        if not s.enabled:
            state = "disabled"
        elif key_setting and not key_ok:
            state = "not_configured"
        elif failing:
            state = "unreachable"
        elif last_ok:
            state = "connected"
        else:
            state = "no_data"
        states[s.name] = {
            "name": s.name, "status": state, "kind": s.kind.value if s.kind else None,
            "key_required": bool(key_setting), "key_configured": key_ok,
            "last_success_at": last_ok, "last_error_at": last_err,
            "last_error": err_msg if failing else None,
        }
    return states


def _collectors(db: Session) -> dict[str, Any]:
    items = []
    for st in source_state(db).values():
        items.append({**st, "last_success_at": _iso(st["last_success_at"]),
                      "last_error_at": _iso(st["last_error_at"])})
    # The synthetic lab collector is not a real feed: never counted as health.
    real = [i for i in items if i["kind"] != "SYNTHETIC" and i["status"] != "disabled"]
    bad = [i for i in real if i["status"] in ("unreachable", "not_configured")]
    ok = [i for i in real if i["status"] == "connected"]
    if not real:
        status = "no_data"
    elif len(ok) == len(real):
        status = "connected"
    elif ok:
        status = "degraded"
    elif bad:
        status = "unreachable"
    else:
        status = "no_data"
    return {"name": "collectors", "kind": "collection", "status": status,
            "detail": f"{len(ok)}/{len(real)} source(s) réelle(s) avec une collecte réussie récente",
            "sources": items}


def _enrichment() -> dict[str, Any]:
    providers = [
        {"name": "AlienVault OTX", "status": "connected" if settings.otx_api_key else "no_data",
         "detail": "clé configurée" if settings.otx_api_key else "sans clé : quota public réduit"},
        {"name": "AbuseIPDB", "status": "connected" if settings.abuseipdb_api_key else "not_configured",
         "detail": "clé configurée" if settings.abuseipdb_api_key else "ABUSEIPDB_API_KEY absente"},
    ]
    # "connected" here means configured: the real call result is stored per IOC
    # (enrichments table) and errors are surfaced in the IOC detail.
    return {"name": "enrichment", "kind": "enrichment",
            "status": "connected" if settings.abuseipdb_api_key else "degraded",
            "detail": "clés présentes (résultat réel visible par IOC)", "providers": providers}


def integrations_status(db: Session, force: bool = False) -> dict[str, Any]:
    with _lock:
        if not force and _cache["value"] and time.monotonic() - _cache["at"] < _CACHE_TTL_S:
            return _cache["value"]

    db_ok, db_detail = check_database()
    value = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "cache_ttl_seconds": int(_CACHE_TTL_S),
        "items": [
            {"name": "postgresql", "kind": "database",
             "status": "connected" if db_ok else "unreachable", "detail": db_detail},
            _n8n(db),
            _collectors(db),
            _enrichment(),
            _misp(),
            _sensor(db, "suricata", "suricata/eve.json"),
            _sensor(db, "wazuh", "wazuh_live/alerts.json"),
        ],
    }
    with _lock:
        _cache.update(at=time.monotonic(), value=value)
    return value
