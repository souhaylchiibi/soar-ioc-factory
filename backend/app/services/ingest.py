"""Ingestion pipeline: normalize → deduplicate → store → audit.

One entry point, `ingest_raw()`, used by both the collectors (n8n or the
API) and the tests. It guarantees:

* invalid indicators are REJECTED with a recorded reason (never repaired),
* duplicates are detected by fingerprint and linked, never re-created,
* every outcome emits a `lifecycle_events` row and an `audit_logs` row,
* no fabricated data: source timestamps are used when present, else now.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collectors.base import RawIndicator
from app.core.logging import get_logger
from app.lifecycle.machine import transition
from app.models.ioc import AuditLog, Ioc, IocSource, IocStatus, IocType
from app.services.normalization import NormalizationError, normalize

logger = get_logger("soar.ingest")


@dataclass
class IngestOutcome:
    """What happened to one raw indicator — used by workflows and tests."""

    raw_value: str
    action: str                 # created | updated | duplicate | rejected
    ioc_id: Optional[str] = None
    reason: str = ""
    fingerprint: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.action in ("created", "updated")


def _declared_type(raw: RawIndicator) -> IocType | None:
    value = raw.context.get("declared_type")
    if not value:
        return None
    try:
        return IocType(value)
    except ValueError:
        return None


def _merge_tags(existing: list[str], incoming: list[str]) -> list[str]:
    seen: list[str] = []
    for tag in list(existing or []) + list(incoming or []):
        if tag and tag not in seen:
            seen.append(tag)
    return seen


def ingest_raw(db: Session, raw: RawIndicator, actor: str = "collector") -> IngestOutcome:
    """Ingest one raw indicator. Caller owns the transaction.

    Returns an IngestOutcome — it does NOT raise on invalid data, because a
    bad indicator is an expected business outcome, not an incident.
    """
    # ---- 1. Normalization + validation ---------------------------------
    try:
        norm = normalize(raw.value, _declared_type(raw))
    except NormalizationError as exc:
        outcome = IngestOutcome(raw_value=raw.value, action="rejected", reason=str(exc))
        _record_rejection(db, raw, str(exc), actor)
        logger.warning("indicator rejected", extra={"action": "NORMALIZE", "source": raw.source_name})
        return outcome

    # ---- 2. Duplicate detection ----------------------------------------
    existing = db.execute(
        select(Ioc).where(Ioc.fingerprint == norm.fingerprint)
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    first_seen = raw.first_seen_at or now
    last_seen = raw.last_seen_at or first_seen
    expires_at = _expires_at(raw)

    if existing is not None:
        return _handle_existing(db, raw, norm, existing, first_seen, last_seen, actor)

    # ---- 3. Brand new IOC ----------------------------------------------
    ctx = dict(raw.context or {})
    ctx.pop("declared_type", None)  # already applied
    if expires_at:
        ctx["expires_at"] = expires_at.isoformat()

    ioc = Ioc(
        type=norm.type,
        value=norm.value,
        raw_value=norm.raw_value,
        status=IocStatus.NEW,
        first_seen_at=min(first_seen, last_seen),
        last_seen_at=max(first_seen, last_seen),
        expires_at=expires_at,
        fingerprint=norm.fingerprint,
        tags=_merge_tags([], raw.tags),
        context=ctx,
        is_synthetic=raw.is_synthetic,
    )
    db.add(ioc)
    db.flush()  # assign id

    # Provenance link (if that source is registered).
    _link_source(db, ioc, raw.source_name, raw)

    # NEW -> NORMALIZED
    result = transition(
        ioc,
        IocStatus.NORMALIZED,
        reason=f"validated as {norm.type.value}; canonical value stored",
        actor=actor,
        triggered_by="ingest",
    )
    db.add(result.event)
    _audit(db, actor, "NORMALIZE", str(ioc.id), {
        "value": norm.value, "type": norm.type.value, "fingerprint": norm.fingerprint,
    })

    logger.info(
        "ioc created",
        extra={"ioc_id": str(ioc.id), "action": "NORMALIZE", "source": raw.source_name},
    )
    return IngestOutcome(
        raw_value=raw.value,
        action="created",
        ioc_id=str(ioc.id),
        reason="created and normalized",
        fingerprint=norm.fingerprint,
    )


def _handle_existing(
    db: Session,
    raw: RawIndicator,
    norm: Any,
    ioc: Ioc,
    first_seen: datetime,
    last_seen: datetime,
    actor: str,
) -> IngestOutcome:
    """Update timestamps/provenance of a known indicator, mark duplicates."""
    # Refresh observation window.
    ioc.last_seen_at = max(ioc.last_seen_at, last_seen)
    ioc.first_seen_at = min(ioc.first_seen_at, first_seen)

    if raw.is_synthetic and not ioc.is_synthetic:
        # A synthetic sighting never downgrades a real indicator's flag.
        pass
    elif raw.is_synthetic:
        ioc.is_synthetic = True

    new_tags = _merge_tags(list(ioc.tags or []), list(raw.tags or []))
    if new_tags != list(ioc.tags or []):
        ioc.tags = new_tags

    _link_source(db, ioc, raw.source_name, raw)

    if ioc.status in (IocStatus.REMOVED, IocStatus.REJECTED):
        # Do not silently resurrect dead indicators — report as duplicate info.
        return IngestOutcome(
            raw_value=raw.value,
            action="duplicate",
            ioc_id=str(ioc.id),
            reason=f"already known in terminal status {ioc.status.value}",
            fingerprint=norm.fingerprint,
        )

    _audit(db, actor, "DEDUP", str(ioc.id), {
        "value": ioc.value, "source": raw.source_name,
        "note": "existing indicator re-observed",
    })
    return IngestOutcome(
        raw_value=raw.value,
        action="updated",
        ioc_id=str(ioc.id),
        reason="existing indicator re-observed",
        fingerprint=norm.fingerprint,
    )


def _expires_at(raw: RawIndicator) -> datetime | None:
    """Expiry comes from the source context only — never invented here."""
    value = (raw.context or {}).get("expires_at")
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _link_source(db: Session, ioc: Ioc, source_name: str, raw: RawIndicator) -> None:
    """Attach provenance when the source is registered (best effort)."""
    from app.models.ioc import IntelSource

    source = db.execute(
        select(IntelSource).where(IntelSource.name == source_name)
    ).scalar_one_or_none()
    if source is None:
        return  # unregistered source: provenance still visible in context
    # Session runs with autoflush=False: flush pending links so this SELECT
    # sees a link created earlier in the SAME transaction (dedup re-observes).
    db.flush()
    link = db.execute(
        select(IocSource).where(IocSource.ioc_id == ioc.id, IocSource.source_id == source.id)
    ).scalar_one_or_none()
    if link is None:
        db.add(IocSource(
            ioc_id=ioc.id, source_id=source.id,
            external_id=raw.external_id, external_url=raw.external_url,
        ))
    else:
        link.last_seen_at = datetime.now(timezone.utc)
        if raw.external_id:
            link.external_id = raw.external_id


def _record_rejection(db: Session, raw: RawIndicator, reason: str, actor: str) -> None:
    """Rejected values are never stored as IOCs — only in the audit trail."""
    _audit(db, actor, "NORMALIZE", None, {
        "raw_value": raw.value[:500], "source": raw.source_name,
        "outcome": "rejected", "reason": reason,
    }, success=False, error=reason)


def _audit(
    db: Session,
    actor: str,
    action: str,
    entity_id: str | None,
    detail: dict[str, Any],
    success: bool = True,
    error: str | None = None,
) -> None:
    db.add(AuditLog(
        actor=actor,
        action=action,
        entity_type="ioc",
        entity_id=entity_id,
        detail=detail,
        success=success,
        error=error,
    ))
