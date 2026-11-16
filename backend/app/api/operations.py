"""Operations API — endpoints driven by the n8n workflows (Phase 4).

Design rules:
* every operation is idempotent and verifiable,
* publication/expiry records are checked before the status changes,
* MISP is not configured yet -> publication target is the local detection
  list; the code refuses to claim success without verification,
* everything is written to the audit trail.
"""
from __future__ import annotations

import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.core.security import Principal, require_analyst
from app.enrichment.otx import OtxEnrichmentProvider
from app.enrichment.service import run_enrichment
from app.lifecycle.machine import LifecycleError, transition
from app.models.account import Report
from app.models.ioc import (
    AuditLog,
    Ioc,
    IocStatus,
    Publication,
)
from app.services.pipeline import expire_due_iocs

logger = get_logger("soar.api.operations")
router = APIRouter(tags=["operations"])


def _mark_source(db: Session, name: str, ok: bool, error: Optional[str] = None) -> None:
    """Keep intel_sources.last_* in sync with the run just recorded in audit."""
    from app.models.ioc import IntelSource

    src = db.execute(select(IntelSource).where(IntelSource.name == name)).scalar_one_or_none()
    if src is None:
        return
    now = datetime.now(timezone.utc)
    if ok:
        src.last_success_at = now
    else:
        src.last_error_at = now
        src.last_error = error


def _ms(t0: float) -> int:
    """Elapsed wall time since t0, in milliseconds (measured, never estimated)."""
    return int((time.perf_counter() - t0) * 1000)


# ------------------------------------------------------------- enrichement --
@router.post("/iocs/collect/run")
def collect_run(
    principal: Principal = Depends(require_analyst),
    db: Session = Depends(get_db),
    source: Optional[str] = Query(None, description="Restreindre à une source"),
    limit: int = Query(50, ge=1, le=300),
) -> dict[str, Any]:
    """Workflow 1: run the collectors and ingest what they return.

    Failures are isolated per source: one dead feed never blocks the others.
    """
    from app.collectors.abusech import (
        MalwareBazaarCollector,
        ThreatFoxCollector,
        UrlhausCollector,
    )
    from app.collectors.blocklist_de import BlocklistDeCollector
    from app.collectors.feodo import FeodoCollector
    from app.collectors.otx import OtxCollector
    from app.collectors.urlscan import UrlscanCollector
    from app.services.ingest import ingest_raw

    catalogue: dict[str, Any] = {
        "feodotracker": FeodoCollector,
        "blocklist_de": BlocklistDeCollector,
        "urlscan": UrlscanCollector,
        # OTX: uses /pulses/subscribed when OTX_API_KEY set (verified live)
        "alienvault_otx": lambda: OtxCollector(api_key=settings.otx_api_key),
        # abuse.ch: require ABUSECH_AUTH_KEY; without it the collector raises
        # (a missing key is reported, never turned into an empty success).
        "urlhaus": lambda: UrlhausCollector(auth_key=settings.abusech_auth_key),
        "threatfox": lambda: ThreatFoxCollector(auth_key=settings.abusech_auth_key),
        "malwarebazaar": lambda: MalwareBazaarCollector(auth_key=settings.abusech_auth_key),
    }
    if source:
        if source not in catalogue:
            raise HTTPException(status_code=400,
                                detail=f"source inconnue: {source}. "
                                       f"disponibles: {', '.join(catalogue)}")
        catalogue = {source: catalogue[source]}

    t0 = time.perf_counter()
    per_source = []
    totals = {"created": 0, "updated": 0, "duplicates": 0, "rejected": 0, "failed": 0}

    for name, cls in catalogue.items():
        entry: dict[str, Any] = {"source": name, "status": "ok"}
        try:
            collector = cls()
            items = list(collector.collect(limit=limit))
            entry["collected"] = len(items)
            local = {"created": 0, "updated": 0, "duplicates": 0, "rejected": 0}
            for raw in items:
                outcome = ingest_raw(db, raw, actor=f"{principal.actor}/{name}")
                key = "duplicates" if outcome.action == "duplicate" else outcome.action
                local[key] = local.get(key, 0) + 1
            entry.update(local)
            for k in totals:
                if k in local:
                    totals[k] += local[k]
            db.add(AuditLog(
                actor=f"{principal.actor}/{name}", action="COLLECT", entity_type="source",
                entity_id=name, detail={"collected": len(items), **local},
                success=True,
            ))
            _mark_source(db, name, ok=True)
        except Exception as exc:
            # Never fake an empty success: record the failure honestly.
            entry["status"] = "failed"
            entry["error"] = str(exc)[:300]
            totals["failed"] += 1
            db.add(AuditLog(
                actor=f"{principal.actor}/{name}", action="COLLECT", entity_type="source",
                entity_id=name, detail={"error": str(exc)[:300]},
                success=False, error=str(exc)[:300],
            ))
            _mark_source(db, name, ok=False, error=str(exc)[:300])
            logger.warning("collector failed", extra={"source": name, "action": "COLLECT"})
        per_source.append(entry)

    duration = _ms(t0)
    db.add(AuditLog(
        actor=principal.actor, role=principal.role, action="COLLECT", entity_type="batch",
        detail={**totals, "sources": len(per_source), "duration_ms": duration},
        success=totals["failed"] == 0,
        error=None if totals["failed"] == 0 else f"{totals['failed']} source(s) en échec",
    ))
    db.commit()
    return {"totals": totals, "sources": per_source, "duration_ms": duration}


# ------------------------------------------------------------- enrichement --
@router.post("/iocs/normalize/run")
def normalize_run(
    principal: Principal = Depends(require_analyst),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    """Workflow 2: catch up normalization/dedup for records stuck in NEW.

    Normalization normally happens synchronously at ingest; this is the
    reconciliation pass for rows that bypassed the pipeline (migration,
    manual insert, partial failure). Stuck records are re-ingested through
    the SAME code path, so validation and dedup rules are identical.
    """
    from app.collectors.base import RawIndicator
    from app.services.ingest import ingest_raw

    t0 = time.perf_counter()
    stuck = db.execute(
        select(Ioc).where(Ioc.status == IocStatus.NEW).order_by(Ioc.created_at).limit(limit)
    ).scalars().all()

    normalized = rejected = failed = 0
    results = []
    for ioc in stuck:
        try:
            outcome = ingest_raw(
                db,
                RawIndicator(
                    value=ioc.raw_value, source_name="reconciliation",
                    first_seen_at=ioc.first_seen_at, last_seen_at=ioc.last_seen_at,
                    tags=list(ioc.tags or []), context=dict(ioc.context or {}),
                    is_synthetic=ioc.is_synthetic,
                ),
                actor=principal.actor,
            )
            if outcome.action in ("created", "updated"):
                normalized += 1
            elif outcome.action == "rejected":
                rejected += 1
                # A value that no longer validates must not stay NEW.
                ioc.status = IocStatus.REJECTED
                db.add(AuditLog(
                    actor=principal.actor, action="NORMALIZE", entity_type="ioc",
                    entity_id=str(ioc.id), success=False, error=outcome.reason,
                    detail={"operation": "reconciliation", "outcome": "rejected"},
                ))
            results.append({"ioc_id": str(ioc.id), "action": outcome.action,
                            "reason": outcome.reason[:120]})
        except Exception as exc:
            failed += 1
            results.append({"ioc_id": str(ioc.id), "action": "error",
                            "reason": str(exc)[:200]})

    # Verification: nothing may remain in NEW after the pass.
    remaining = db.execute(select(func.count(Ioc.id)).where(Ioc.status == IocStatus.NEW)).scalar() or 0
    db.add(AuditLog(
        actor=principal.actor, action="NORMALIZE", entity_type="batch",
        detail={"found": len(stuck), "normalized": normalized,
                "rejected": rejected, "failed": failed,
                "remaining_new": int(remaining), "duration_ms": _ms(t0)},
        success=failed == 0,
        error=None if failed == 0 else f"{failed} failures",
    ))
    db.commit()
    return {"found": len(stuck), "normalized": normalized, "rejected": rejected,
            "failed": failed, "remaining_new": int(remaining), "results": results}


@router.post("/iocs/detections/ingest")
def ingest_sensor_alerts(
    principal: Principal = Depends(require_analyst),
    db: Session = Depends(get_db),
    sensor: str = Query(..., pattern="^(suricata|wazuh)$"),
    path: Optional[str] = Query(None, description="Chemin du fichier eve.json/alerts.json"),
) -> dict[str, Any]:
    """Workflow 6: read IDS alerts and count matches against tracked IOCs.

    Alerts whose indicator is NOT in the inventory are reported but never
    stored as IOCs (collection owns ingestion — no silent insertion).
    """
    from app.integrations.suricata import parse_eve
    from app.integrations.suricata import trackable_value as s_val
    from app.integrations.wazuh import parse_alerts_json
    from app.models.ioc import Detection

    default_paths = {
        "suricata": "/sensor/suricata/eve.json",
        # wazuh_live = volume externe partagé avec le conteneur wazuh
        "wazuh": "/sensor/wazuh_live/alerts.json",
    }
    t0 = time.perf_counter()
    target = Path(path or default_paths[sensor])
    # Path traversal guard: only files under the read-only sensor mounts.
    root = Path(settings.sensor_root).resolve()
    try:
        resolved = target.resolve()
    except OSError:
        raise HTTPException(status_code=400, detail="chemin de capteur invalide") from None
    if resolved != root and root not in resolved.parents:
        raise HTTPException(status_code=400,
                            detail=f"chemin refusé : doit se trouver sous {settings.sensor_root}")
    target = resolved

    if not target.exists():
        return {"sensor": sensor, "status": "no_file",
                "detail": f"{target} absent — capteur non actif (profil Docker?)",
                "matched": 0, "untracked": 0, "alerts": 0}

    if sensor == "suricata":
        alerts = parse_eve(target)
        candidates = [(a.timestamp, s_val(a), a.signature, str(a.sid), a.raw) for a in alerts]
    else:
        walerts = parse_alerts_json(target)
        # Keep the evidence needed to qualify the alert later (level, text).
        candidates = [(a.timestamp, a.src_ip, a.description, str(a.rule_id),
                       {"full_log": a.full_log[:500], "rule": {"id": a.rule_id, "level": a.rule_level,
                                                              "description": a.description[:200]},
                        "timestamp": a.timestamp.isoformat()})
                      for a in walerts]

    matched = untracked = duplicates = 0
    seen_keys: set[tuple] = set()
    results = []

    for ts, value, signature, rule_id, raw in candidates:
        if not value:
            continue
        ioc = db.execute(select(Ioc).where(Ioc.value == value)).scalar_one_or_none()
        if ioc is None:
            untracked += 1
            continue

        # Dedup identical (ioc, sensor, rule, minute) alerts.
        key = (ioc.id, sensor, rule_id, ts.replace(second=0, microsecond=0))
        if key in seen_keys:
            duplicates += 1
            continue
        seen_keys.add(key)

        db.add(Detection(
            ioc_id=ioc.id, sensor=sensor, rule_id=rule_id,
            raw_event=raw if isinstance(raw, dict) else {"raw": str(raw)},
            matched_at=ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc),
        ))
        ioc.detection_count += 1
        ioc.last_detection_at = max(ioc.last_detection_at or ts, ts)
        matched += 1
        results.append({"ioc_id": str(ioc.id), "value": value,
                        "signature": signature[:80], "rule_id": rule_id,
                        "matched_at": ts.isoformat()})

    db.add(AuditLog(
        actor=f"{principal.actor}/{sensor}", action="OBSERVE", entity_type="batch",
        detail={"alerts": len(candidates), "matched": matched,
                "untracked": untracked, "duplicates_skipped": duplicates,
                "file": str(target), "duration_ms": _ms(t0)},
        success=True,
    ))
    db.commit()
    return {"sensor": sensor, "status": "ok", "alerts": len(candidates),
            "matched": matched, "untracked": untracked,
            "duplicates_skipped": duplicates, "results": results[:50]}


@router.get("/iocs/detections/recent")
def recent_detections(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    sensor: Optional[str] = None,
) -> dict[str, Any]:
    """Workflow 6: latest observed matches (from Wazuh/Suricata/manual)."""
    from app.models.ioc import Detection

    stmt = select(Detection).order_by(Detection.matched_at.desc()).limit(limit)
    if sensor:
        stmt = stmt.where(Detection.sensor == sensor)
    rows = db.execute(stmt).scalars().all()

    fp_count = sum(1 for d in rows if d.is_false_positive)
    return {
        "count": len(rows),
        "false_positives_in_window": fp_count,
        "detections": [
            {"id": str(d.id), "ioc_id": str(d.ioc_id), "sensor": d.sensor,
             "rule_id": d.rule_id, "matched_at": d.matched_at.isoformat(),
             "is_false_positive": d.is_false_positive}
            for d in rows
        ],
    }


@router.post("/iocs/enrich/run")
def enrich_run(
    principal: Principal = Depends(require_analyst),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    force: bool = False,
) -> dict[str, Any]:
    """Workflow 3: enrich NORMALIZED IOCs through registered providers."""
    t0 = time.perf_counter()
    targets = db.execute(
        select(Ioc)
        .where(Ioc.status == IocStatus.NORMALIZED, Ioc.is_synthetic.is_(False))
        .order_by(Ioc.created_at)
        .limit(limit)
    ).scalars().all()

    # OTX works without a key (rate-limited); with a key it unlocks
    # /pulses/subscribed (verified live). AbuseIPDB requires its key.
    providers: list[Any] = [OtxEnrichmentProvider(api_key=settings.otx_api_key)]
    if settings.abuseipdb_api_key:
        try:
            from app.enrichment.abuseipdb import AbuseIpdbProvider
            providers.append(AbuseIpdbProvider(api_key=settings.abuseipdb_api_key))
        except ValueError:  # pragma: no cover - config guard
            logger.warning("abuseipdb skipped", extra={"action": "ENRICH"})

    enriched, failed = 0, 0
    results = []
    for ioc in targets:
        summary = run_enrichment(db, ioc, providers, force=force)
        errors = [f"{e.provider}: {e.error}" for e in summary.errors]
        if summary.verdicts:
            try:
                tr = transition(
                    ioc, IocStatus.ENRICHED,
                    reason=f"enrichment: {', '.join(summary.verdicts)} "
                           f"(providers: {', '.join(r.provider for r in summary.results if r.ok)})",
                    actor=principal.actor, triggered_by=principal.actor,
                )
                db.add(tr.event)
                enriched += 1
            except LifecycleError as exc:
                errors.append(str(exc))
        if errors:
            failed += 1
        results.append({
            "ioc_id": str(ioc.id), "value": ioc.value,
            "verdicts": summary.verdicts, "errors": errors,
        })

    db.add(AuditLog(
        actor=principal.actor, action="ENRICH", entity_type="batch",
        detail={"targets": len(targets), "enriched": enriched, "with_errors": failed,
                "duration_ms": _ms(t0)},
        success=True, error=None if failed == 0 else f"{failed} ioc(s) with provider errors",
    ))
    db.commit()
    return {"targets": len(targets), "enriched": enriched, "with_errors": failed,
            "results": results}


# ------------------------------------------------------------ publication ---
@router.post("/iocs/publish/run")
def publish_run(
    principal: Principal = Depends(require_analyst),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    """Workflow 5: publish high-score IOCs to the detection list.

    Verification: after writing, we read the publication back and only mark
    the transition `verified` if the record really exists.
    """
    t0 = time.perf_counter()
    targets = db.execute(
        select(Ioc)
        .where(Ioc.status == IocStatus.PUBLISHED)
        .order_by(Ioc.score.desc().nulls_last())
        .limit(limit)
    ).scalars().all()

    published, verified, failed = 0, 0, 0
    results = []
    for ioc in targets:
        already = db.execute(
            select(Publication).where(
                Publication.ioc_id == ioc.id,
                Publication.target == "detection_list",
                Publication.revoked_at.is_(None),
            )
        ).scalar_one_or_none()
        if already is not None:
            results.append({"ioc_id": str(ioc.id), "action": "already_published",
                            "ref": already.target_ref})
            continue

        # Target: local detection list (MISP comes in Phase 5).
        target_ref = f"detection-list://{ioc.type.value.lower()}/{ioc.id}"
        pub = Publication(ioc_id=ioc.id, target="detection_list",
                          target_ref=target_ref, status="pending",
                          detail={"value": ioc.value, "score": ioc.score})
        db.add(pub)
        db.flush()

        # ---- Verification: read it back from the database ----
        check = db.execute(
            select(Publication).where(Publication.id == pub.id)
        ).scalar_one_or_none()
        if check is None or check.status != "pending":
            failed += 1
            results.append({"ioc_id": str(ioc.id), "action": "failed",
                            "error": "publication not readable after insert"})
            continue

        check.status = "verified"
        pub.status = "verified"
        published += 1
        verified += 1
        results.append({"ioc_id": str(ioc.id), "action": "published",
                        "ref": target_ref, "verified": True,
                        "value": ioc.value, "score": ioc.score})

    db.add(AuditLog(
        actor=principal.actor, action="PUBLISH", entity_type="batch",
        detail={"candidates": len(targets), "published": published, "verified": verified,
                "failed": failed, "target": "detection_list", "duration_ms": _ms(t0)},
        success=failed == 0, error=None if failed == 0 else f"{failed} failures",
    ))
    db.commit()
    return {"candidates": len(targets), "published": published, "verified": verified,
            "failed": failed, "results": results}


# -------------------------------------------------------------- expiration --
@router.post("/iocs/publish/misp/run")
def publish_misp_run(
    principal: Principal = Depends(require_analyst),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    """Workflow 5 (MISP leg): publish PUBLISHED IOCs to MISP, verified.

    Without MISP_URL/MISP_KEY the endpoint reports `skipped` (never fakes a
    success). With them, each attribute is confirmed by read-back before the
    publication row is marked `verified`.
    """
    from app.services.misp_ops import publish_pending_to_misp

    return publish_pending_to_misp(db, limit=limit)


@router.post("/iocs/expire/run")
def expire_run(principal: Principal = Depends(require_analyst), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Workflow 7: mark due indicators EXPIRED (removal is separate+verified)."""
    t0 = time.perf_counter()
    results = expire_due_iocs(db, actor=principal.actor)
    expired = [r for r in results if r.get("action") == "expired"]
    errors = [r for r in results if r.get("action") == "error"]
    db.add(AuditLog(
        actor=principal.actor, role=principal.role, action="EXPIRE", entity_type="batch",
        detail={"expired": len(expired), "errors": len(errors), "duration_ms": _ms(t0)},
        success=not errors, error=None if not errors else f"{len(errors)} erreur(s)",
    ))
    db.commit()
    return {"expired": len(expired), "errors":
            [r for r in results if r.get("action") == "error"], "results": results}


@router.post("/iocs/remove/run")
def remove_run(principal: Principal = Depends(require_analyst), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Workflow 7 (second half): revoke publications, then mark REMOVED.

    The REMOVED status requires a *verified* revocation: we re-read every
    publication after revocation and refuse to lie if one is still active.
    """
    t0 = time.perf_counter()
    expired = db.execute(
        select(Ioc).where(Ioc.status == IocStatus.EXPIRED)
    ).scalars().all()

    from app.services import misp_ops

    removed, failed = 0, 0
    results = []
    for ioc in expired:
        # 1. Revoke every active publication (MISP = remote + verified).
        pubs = db.execute(
            select(Publication).where(
                Publication.ioc_id == ioc.id, Publication.revoked_at.is_(None)
            )
        ).scalars().all()
        now = datetime.now(timezone.utc)

        remote_ok = True
        for pub in pubs:
            if pub.target == misp_ops.MISP_TARGET:
                # Remote deletion must be CONFIRMED by MISP (read-back).
                if not misp_ops.revoke_misp_attribute(db, pub, ioc):
                    remote_ok = False
                    continue
            else:
                pub.status = "revoked"
                pub.revoked_at = now
        db.flush()

        # 2. Verify revocation by reading back.
        still_active = db.execute(
            select(func.count(Publication.id)).where(
                Publication.ioc_id == ioc.id,
                Publication.revoked_at.is_(None),
            )
        ).scalar() or 0

        if still_active or not remote_ok:
            failed += 1
            results.append({"ioc_id": str(ioc.id), "action": "failed",
                            "error": f"{still_active} publication(s) encore actives"
                                     + ("" if remote_ok else " / MISP retrait non confirme")})
            continue

        # 3. Transition with verification proof.
        try:
            tr = transition(
                ioc, IocStatus.REMOVED,
                reason=f"expiry enforced; {len(pubs)} publication(s) revoked",
                actor=principal.actor, triggered_by=principal.actor,
                verified=True,
                verification_detail={"revoked_publications": len(pubs),
                                     "still_active": int(still_active)},
            )
            db.add(tr.event)
            db.add(AuditLog(
                actor=principal.actor, action="REMOVE", entity_type="ioc",
                entity_id=str(ioc.id),
                detail={"value": ioc.value, "revoked": len(pubs), "verified": True},
            ))
            removed += 1
            results.append({"ioc_id": str(ioc.id), "action": "removed",
                            "revoked_publications": len(pubs), "verified": True})
        except LifecycleError as exc:
            failed += 1
            results.append({"ioc_id": str(ioc.id), "action": "failed", "error": str(exc)})

    db.add(AuditLog(
        actor=principal.actor, role=principal.role, action="REMOVE", entity_type="batch",
        detail={"candidates": len(expired), "removed": removed, "failed": failed,
                "duration_ms": _ms(t0)},
        success=failed == 0, error=None if failed == 0 else f"{failed} retrait(s) non confirmé(s)",
    ))
    db.commit()
    return {"candidates": len(expired), "removed": removed, "failed": failed,
            "results": results}


@router.patch("/iocs/{ioc_id}")
def update_ioc(
    ioc_id: uuid.UUID,
    principal: Principal = Depends(require_analyst),
    db: Session = Depends(get_db),
    expires_at: Optional[datetime] = None,
    add_tags: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Analyst override: adjust expiry / tags. Always audited.

    Used to shorten an indicator's validity (or extend it) — a routine SOC
    operation. The new value is stored verbatim; nothing is inferred.
    """
    ioc = db.get(Ioc, ioc_id)
    if ioc is None:
        raise HTTPException(status_code=404, detail="IOC introuvable")
    if ioc.status in (IocStatus.REMOVED, IocStatus.REJECTED, IocStatus.DUPLICATE):
        raise HTTPException(status_code=409,
                            detail=f"statut terminal {ioc.status.value}: modification refusée")

    changes: dict[str, Any] = {}
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        changes["expires_at"] = {"from": ioc.expires_at.isoformat() if ioc.expires_at else None,
                                 "to": expires_at.isoformat()}
        ioc.expires_at = expires_at
    if add_tags:
        merged = list(dict.fromkeys(list(ioc.tags or []) + add_tags))
        if merged != list(ioc.tags or []):
            changes["tags"] = {"from": ioc.tags, "to": merged}
            ioc.tags = merged

    if not changes:
        raise HTTPException(status_code=400, detail="aucune modification fournie")

    db.add(AuditLog(
        actor=principal.actor, role=principal.role, action="CONFIG_CHANGE", entity_type="ioc", entity_id=str(ioc.id),
        detail={"operation": "override", "changes": changes},
    ))
    db.commit()
    return {"ioc_id": str(ioc.id), "changes": changes, "status": ioc.status.value}


# -------------------------------------------------------------- détections --
@router.post("/iocs/{ioc_id}/detections")
def record_detection(
    ioc_id: uuid.UUID,
    principal: Principal = Depends(require_analyst),
    db: Session = Depends(get_db),
    sensor: str = Query(..., pattern="^(wazuh|suricata|misp|manual)$"),
    rule_id: Optional[str] = None,
    is_false_positive: Optional[bool] = None,
) -> dict[str, Any]:
    """Workflow 6: record an observed match from a detection system."""
    from app.models.ioc import Detection

    ioc = db.get(Ioc, ioc_id)
    if ioc is None:
        raise HTTPException(status_code=404, detail="IOC introuvable")

    db.add(Detection(
        ioc_id=ioc.id, sensor=sensor, rule_id=rule_id,
        raw_event={"source": sensor, "rule": rule_id,
                   "recorded_by": "operations-api"},
        is_false_positive=is_false_positive,
    ))
    ioc.detection_count += 1
    ioc.last_detection_at = datetime.now(timezone.utc)
    if is_false_positive:
        ioc.false_positive_count += 1

    db.add(AuditLog(
        actor=f"{principal.actor}/{sensor}", action="OBSERVE", entity_type="ioc",
        entity_id=str(ioc.id),
        detail={"detection_count": ioc.detection_count,
                "false_positive": bool(is_false_positive)},
    ))
    db.commit()
    return {"ioc_id": str(ioc.id), "detection_count": ioc.detection_count,
            "false_positive_count": ioc.false_positive_count,
            "score": ioc.score, "status": ioc.status.value}


# ---------------------------------------------------------------- rapports --
@router.post("/reports/daily")
def generate_daily_report(
    principal: Principal = Depends(require_analyst),
    db: Session = Depends(get_db),
    report_date: Optional[date] = None,
) -> dict[str, Any]:
    """Workflow 8: compute the daily report from real database figures."""
    from app.api.iocs import dashboard_stats, source_stats

    day = report_date or datetime.now(timezone.utc).date()
    stats = dashboard_stats(db)
    sources = source_stats(db)

    payload = {
        "date": day.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "total": stats.total_iocs, "active": stats.active_iocs,
            "published": stats.published_iocs, "monitored": stats.monitored_iocs,
            "rejected": stats.rejected_iocs, "expired": stats.expired_iocs,
            "removed": stats.removed_iocs, "review": stats.review_required,
        },
        "quality": {
            "dedup_rate": stats.dedup_rate,
            "avg_score": stats.avg_score,
            "avg_processing_seconds": stats.avg_processing_seconds,
            "false_positives": stats.false_positives,
            "detections": stats.total_detections,
        },
        "by_type": stats.by_type,
        "by_status": stats.by_status,
        "score_distribution": stats.score_distribution,
        "sources": [
            {"name": s.name, "ioc_count": s.ioc_count,
             "reliability": s.reliability, "enabled": s.enabled,
             "last_success_at": s.last_success_at.isoformat() if s.last_success_at else None}
            for s in sources
        ],
        "synthetic_iocs": stats.synthetic_iocs,
    }

    existing = db.execute(
        select(Report).where(Report.report_date == day, Report.kind == "daily")
    ).scalar_one_or_none()
    if existing is not None:
        existing.payload = payload
        report_id = str(existing.id)
        action = "updated"
    else:
        rep = Report(report_date=day, kind="daily", payload=payload)
        db.add(rep)
        db.flush()
        report_id = str(rep.id)
        action = "created"

    db.add(AuditLog(
        actor=principal.actor, action="EXPORT", entity_type="report",
        entity_id=report_id, detail={"date": day.isoformat(), "action": action},
    ))
    db.commit()
    return {"report_id": report_id, "action": action, "payload": payload}


@router.get("/reports/daily")
def get_daily_report(db: Session = Depends(get_db),
                     report_date: Optional[date] = None) -> dict[str, Any]:
    day = report_date or datetime.now(timezone.utc).date()
    rep = db.execute(
        select(Report).where(Report.report_date == day, Report.kind == "daily")
    ).scalar_one_or_none()
    if rep is None:
        raise HTTPException(status_code=404, detail="Rapport introuvable pour cette date")
    return {"report_id": str(rep.id), "date": rep.report_date.isoformat(),
            "generated_at": rep.generated_at.isoformat(), "payload": rep.payload}
