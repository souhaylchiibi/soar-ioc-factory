"""SOC console endpoints: integrations, notifications, lifecycle funnel,
timeline, detection center, run history, IOC activity and global search.

Read-only except detection review. Every figure is a query on PostgreSQL
(or a live probe for integrations); nothing is estimated or padded.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import Principal, client_ip, require_analyst
from app.models.ioc import (
    AuditLog,
    Detection,
    IntelSource,
    Ioc,
    IocSource,
    IocStatus,
    LifecycleEvent,
    Publication,
    ScoreHistory,
)
from app.services.integrations_status import integrations_status, source_state

router = APIRouter(tags=["soc"])

# Pipeline stages, in order, with the audit action / status that proves them.
STAGES = [
    ("collect", "Collecte", "audit", "COLLECT"),
    ("normalize", "Normalisation", "audit", "NORMALIZE"),
    ("dedup", "Déduplication", "audit", "DEDUP"),
    ("enrich", "Enrichissement", "status", IocStatus.ENRICHED),
    ("score", "Scoring", "status", IocStatus.SCORED),
    ("decide", "Décision", "decision", None),
    ("publish", "Publication", "status", IocStatus.PUBLISHED),
    ("monitor", "Surveillance", "status", IocStatus.MONITORED),
    ("expire", "Expiration", "status", IocStatus.EXPIRED),
    ("remove", "Retrait vérifié", "status", IocStatus.REMOVED),
]

RUN_ACTIONS = ("COLLECT", "NORMALIZE", "ENRICH", "SCORE", "PUBLISH", "OBSERVE",
               "EXPIRE", "REMOVE", "EXPORT")


def _iso(ts: Optional[datetime]) -> Optional[str]:
    return ts.isoformat() if ts else None


# ----------------------------------------------------------- integrations --
@router.get("/integrations/status")
def get_integrations(db: Session = Depends(get_db), refresh: bool = False) -> dict[str, Any]:
    return integrations_status(db, force=refresh)


# ---------------------------------------------------------- notifications --
@router.get("/notifications")
def notifications(db: Session = Depends(get_db),
                  hours: int = Query(48, ge=1, le=720),
                  limit: int = Query(30, ge=1, le=100)) -> dict[str, Any]:
    """Real events worth an analyst's attention: failures, new detections,
    lockouts, items awaiting review. Read state is kept client-side."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    items: list[dict[str, Any]] = []

    for a in db.execute(
        select(AuditLog).where(AuditLog.occurred_at >= since, AuditLog.success.is_(False))
        .order_by(AuditLog.id.desc()).limit(limit)
    ).scalars():
        items.append({
            "id": f"audit-{a.id}", "severity": "high" if a.action in ("PUBLISH", "REMOVE") else "medium",
            "category": "failure", "title": f"Échec {a.action}",
            "message": (a.error or "")[:200] or f"{a.actor} — {a.entity_type or ''}",
            "occurred_at": a.occurred_at.isoformat(), "link": "/audit",
        })

    for d, ioc_value in db.execute(
        select(Detection, Ioc.value).join(Ioc, Ioc.id == Detection.ioc_id)
        .where(Detection.matched_at >= since).order_by(Detection.matched_at.desc()).limit(limit)
    ).all():
        items.append({
            "id": f"det-{d.id}", "severity": "high", "category": "detection",
            "title": f"Détection {d.sensor}", "message": f"{ioc_value} · règle {d.rule_id or '—'}",
            "occurred_at": d.matched_at.isoformat(), "link": f"/iocs/{d.ioc_id}",
        })

    review = db.execute(select(func.count(Ioc.id)).where(Ioc.status == IocStatus.REVIEW_REQUIRED)).scalar() or 0
    if review:
        items.append({
            "id": f"review-{review}", "severity": "low", "category": "review",
            "title": "IOC à revoir", "message": f"{review} indicateur(s) attendent une décision analyste",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "link": "/threat-intel?status=REVIEW_REQUIRED",
        })

    items.sort(key=lambda i: i["occurred_at"], reverse=True)
    return {"window_hours": hours, "count": len(items), "items": items[:limit]}


# ------------------------------------------------------------- lifecycle ---
@router.get("/lifecycle/funnel")
def lifecycle_funnel(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Throughput of each pipeline stage, with its proof source.

    * audit stages count recorded operations (COLLECT counts collected items)
    * status stages count IOCs that *entered* the state (lifecycle_events)
    * `current` is how many IOCs sit in that state right now
    """
    entered = {s: n for s, n in db.execute(
        select(LifecycleEvent.to_status, func.count(func.distinct(LifecycleEvent.ioc_id)))
        .group_by(LifecycleEvent.to_status)).all()}
    current = {s: n for s, n in db.execute(
        select(Ioc.status, func.count(Ioc.id)).group_by(Ioc.status)).all()}

    collected = 0
    for detail, in db.execute(select(AuditLog.detail).where(
            AuditLog.action == "COLLECT", AuditLog.entity_type == "source",
            AuditLog.success.is_(True))).all():
        if isinstance(detail, dict):
            collected += int(detail.get("collected") or 0)

    audit_counts = {a: n for a, n in db.execute(
        select(AuditLog.action, func.count(AuditLog.id))
        .where(AuditLog.action.in_(["NORMALIZE", "DEDUP"]), AuditLog.entity_type == "ioc")
        .group_by(AuditLog.action)).all()}

    decided = {
        "publish": entered.get(IocStatus.PUBLISHED, 0),
        "monitor": entered.get(IocStatus.MONITORED, 0),
        "reject": entered.get(IocStatus.REJECTED, 0),
        "review": entered.get(IocStatus.REVIEW_REQUIRED, 0),
    }
    stages = []
    for key, label, kind, ref in STAGES:
        if kind == "audit":
            value = collected if ref == "COLLECT" else int(audit_counts.get(ref, 0))
            proof = f"audit_logs.action='{ref}'"
            now = None
        elif kind == "decision":
            value = sum(decided.values())
            proof = "lifecycle_events.to_status IN (PUBLISHED, MONITORED, REJECTED, REVIEW_REQUIRED)"
            now = None
        else:
            value = int(entered.get(ref, 0))
            proof = f"lifecycle_events.to_status='{ref.value}'"
            now = int(current.get(ref, 0))
        stages.append({"key": key, "label": label, "count": value, "current": now, "proof": proof})

    verified_removals = db.execute(select(func.count(LifecycleEvent.id)).where(
        LifecycleEvent.to_status == IocStatus.REMOVED, LifecycleEvent.verified.is_(True))).scalar() or 0
    return {
        "stages": stages,
        "decisions": decided,
        "current": {k.value: int(v) for k, v in current.items()},
        "verified_removals": int(verified_removals),
        "collected_items": collected,
    }


# -------------------------------------------------------------- timeline ---
@router.get("/stats/timeline")
def timeline(db: Session = Depends(get_db), days: int = Query(30, ge=7, le=180)) -> dict[str, Any]:
    """Daily series: IOCs created, decisions (from lifecycle events), detections."""
    since = (datetime.now(timezone.utc) - timedelta(days=days - 1)).date()
    series: dict[str, dict[str, int]] = {}
    for i in range(days):
        d = (since + timedelta(days=i)).isoformat()
        series[d] = {"created": 0, "published": 0, "monitored": 0, "rejected": 0,
                     "expired": 0, "detections": 0}

    day = func.date(Ioc.created_at)
    for d, n in db.execute(select(day, func.count(Ioc.id)).where(day >= since).group_by(day)).all():
        series[d.isoformat()]["created"] = int(n)

    lday = func.date(LifecycleEvent.created_at)
    mapping = {IocStatus.PUBLISHED: "published", IocStatus.MONITORED: "monitored",
               IocStatus.REJECTED: "rejected", IocStatus.EXPIRED: "expired"}
    for d, status, n in db.execute(
        select(lday, LifecycleEvent.to_status, func.count(LifecycleEvent.id))
        .where(lday >= since, LifecycleEvent.to_status.in_(list(mapping)))
        .group_by(lday, LifecycleEvent.to_status)).all():
        series[d.isoformat()][mapping[status]] += int(n)

    dday = func.date(Detection.matched_at)
    for d, n in db.execute(select(dday, func.count(Detection.id)).where(dday >= since).group_by(dday)).all():
        if d.isoformat() in series:
            series[d.isoformat()]["detections"] = int(n)

    return {"days": days, "series": [{"date": k, **v} for k, v in series.items()]}


# --------------------------------------------------------------- sources ---
@router.get("/sources")
def sources_overview(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Every registered source with yield, health and its last collection runs."""
    status = source_state(db)
    counts = {sid: n for sid, n in db.execute(
        select(IocSource.source_id, func.count(func.distinct(IocSource.ioc_id)))
        .group_by(IocSource.source_id)).all()}
    since = datetime.now(timezone.utc) - timedelta(days=30)
    runs = db.execute(
        select(AuditLog.entity_id, func.count(AuditLog.id),
               func.count(AuditLog.id).filter(AuditLog.success.is_(False)))
        .where(AuditLog.action == "COLLECT", AuditLog.entity_type == "source", AuditLog.occurred_at >= since)
        .group_by(AuditLog.entity_id)).all()
    run_stats = {name: {"runs_30d": int(t), "failures_30d": int(f)} for name, t, f in runs}

    out = []
    for s in db.execute(select(IntelSource).order_by(IntelSource.name)).scalars():
        st = status.get(s.name, {})
        out.append({
            "id": str(s.id), "name": s.name, "url": s.url, "kind": s.kind.value if s.kind else None,
            "provenance_group": s.provenance_group, "reliability": s.reliability,
            "enabled": s.enabled, "requires_api_key": s.requires_api_key,
            "rate_limit_rpm": s.rate_limit_rpm, "ioc_count": int(counts.get(s.id, 0)),
            "last_success_at": _iso(st.get("last_success_at")), "last_error_at": _iso(st.get("last_error_at")),
            "last_error": st.get("last_error"), "connection": st.get("status", "no_data"),
            "key_configured": st.get("key_configured"),
            **run_stats.get(s.name, {"runs_30d": 0, "failures_30d": 0}),
        })
    return {"count": len(out), "sources": out}


@router.get("/sources/{name}/runs")
def source_runs(name: str, db: Session = Depends(get_db),
                limit: int = Query(30, ge=1, le=200)) -> dict[str, Any]:
    rows = db.execute(
        select(AuditLog).where(AuditLog.action == "COLLECT", AuditLog.entity_type == "source",
                               AuditLog.entity_id == name)
        .order_by(AuditLog.id.desc()).limit(limit)).scalars().all()
    return {"source": name, "runs": [
        {"id": r.id, "occurred_at": r.occurred_at.isoformat(), "actor": r.actor,
         "success": r.success, "error": r.error, "detail": r.detail} for r in rows]}


# ------------------------------------------------------- detection center --
def _obj(value: Any) -> dict:
    """Sensor payloads are heterogeneous (manual entries store strings)."""
    return value if isinstance(value, dict) else {}


def severity_of(sensor: str, raw: Any) -> Optional[str]:
    """Severity as stated by the sensor itself; None when it gave none."""
    if not isinstance(raw, dict):
        return None
    if sensor == "suricata":
        sev = _obj(raw.get("alert")).get("severity")
        return {1: "high", 2: "medium", 3: "low"}.get(sev) if isinstance(sev, int) else None
    if sensor == "wazuh":
        level = _obj(raw.get("rule")).get("level")
        if not isinstance(level, int):
            return None
        return "critical" if level >= 12 else "high" if level >= 7 else "medium" if level >= 4 else "low"
    return None


def _detection_out(d: Detection, ioc: Ioc) -> dict[str, Any]:
    raw = d.raw_event if isinstance(d.raw_event, dict) else {}
    signature = _obj(raw.get("alert")).get("signature") or _obj(raw.get("rule")).get("description")
    triage = ("false_positive" if d.is_false_positive is True
              else "confirmed" if d.is_false_positive is False else "pending")
    return {
        "id": str(d.id), "ioc_id": str(d.ioc_id), "ioc_value": ioc.value, "ioc_type": ioc.type.value,
        "ioc_risk": ioc.risk_level.value if ioc.risk_level else None, "ioc_status": ioc.status.value,
        "ioc_synthetic": ioc.is_synthetic,
        "sensor": d.sensor, "rule_id": d.rule_id, "signature": signature,
        "severity": severity_of(d.sensor, raw), "matched_at": d.matched_at.isoformat(),
        "triage": triage, "reviewed_by": d.reviewed_by, "review_note": d.review_note,
        "evidence": raw,
    }


@router.get("/detections")
def list_detections(
    db: Session = Depends(get_db),
    sensor: Optional[str] = Query(None, pattern="^(suricata|wazuh|misp|manual)$"),
    triage: Optional[str] = Query(None, pattern="^(pending|confirmed|false_positive)$"),
    q: Optional[str] = Query(None, max_length=200),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    clauses = []
    if sensor:
        clauses.append(Detection.sensor == sensor)
    if triage == "pending":
        clauses.append(Detection.is_false_positive.is_(None))
    elif triage == "confirmed":
        clauses.append(Detection.is_false_positive.is_(False))
    elif triage == "false_positive":
        clauses.append(Detection.is_false_positive.is_(True))
    if q:
        clauses.append(or_(Ioc.value.ilike(f"%{q}%"), Detection.rule_id.ilike(f"%{q}%")))

    base = select(Detection, Ioc).join(Ioc, Ioc.id == Detection.ioc_id).where(*clauses)
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0
    rows = db.execute(base.order_by(Detection.matched_at.desc()).offset(offset).limit(limit)).all()
    by_sensor = {s: int(n) for s, n in db.execute(
        select(Detection.sensor, func.count(Detection.id)).group_by(Detection.sensor)).all()}
    by_triage = {k: int(v or 0) for k, v in db.execute(select(
        func.count(Detection.id).filter(Detection.is_false_positive.is_(None)).label("pending"),
        func.count(Detection.id).filter(Detection.is_false_positive.is_(False)).label("confirmed"),
        func.count(Detection.id).filter(Detection.is_false_positive.is_(True)).label("false_positive"),
    )).one()._asdict().items()}
    return {"total": int(total), "offset": offset, "limit": limit, "by_sensor": by_sensor,
            "by_triage": by_triage, "items": [_detection_out(d, i) for d, i in rows]}


class DetectionReview(BaseModel):
    verdict: str = Field(..., pattern="^(confirmed|false_positive)$")
    note: Optional[str] = Field(None, max_length=500)


@router.post("/detections/{detection_id}/review")
def review_detection(detection_id: uuid.UUID, body: DetectionReview, request: Request,
                     db: Session = Depends(get_db),
                     principal: Principal = Depends(require_analyst)) -> dict[str, Any]:
    """Analyst triage. A false positive feeds the scoring penalty of the IOC."""
    d = db.get(Detection, detection_id)
    if d is None:
        raise HTTPException(status_code=404, detail="détection introuvable")
    ioc = db.get(Ioc, d.ioc_id)
    was_fp = d.is_false_positive is True
    is_fp = body.verdict == "false_positive"
    d.is_false_positive = is_fp
    d.reviewed_by = principal.actor
    d.review_note = body.note
    # Keep the IOC counter consistent with the per-detection truth.
    if is_fp and not was_fp:
        ioc.false_positive_count += 1
    elif was_fp and not is_fp and ioc.false_positive_count > 0:
        ioc.false_positive_count -= 1
    db.add(AuditLog(actor=principal.actor, role=principal.role, action="DETECTION_REVIEW",
                    entity_type="detection", entity_id=str(d.id), ip_address=client_ip(request),
                    detail={"ioc_id": str(ioc.id), "verdict": body.verdict, "note": body.note}))
    db.commit()
    return _detection_out(d, ioc)


# ----------------------------------------------------------- run history ---
@router.get("/workflows/runs")
def workflow_runs(
    db: Session = Depends(get_db),
    action: Optional[str] = Query(None, max_length=20),
    actor: Optional[str] = Query(None, max_length=64),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """One row per pipeline run (batch audit entries), with measured duration
    when the run recorded it (`duration_ms` absent on older runs)."""
    clauses = [AuditLog.entity_type == "batch", AuditLog.action.in_(RUN_ACTIONS)]
    if action:
        clauses.append(AuditLog.action == action)
    if actor:
        clauses.append(AuditLog.actor.like(f"{actor}%"))
    total = db.execute(select(func.count(AuditLog.id)).where(*clauses)).scalar() or 0
    rows = db.execute(select(AuditLog).where(*clauses).order_by(AuditLog.id.desc())
                      .offset(offset).limit(limit)).scalars().all()
    failed_total = db.execute(select(func.count(AuditLog.id))
                              .where(*clauses, AuditLog.success.is_(False))).scalar() or 0
    durations = [int(r.detail.get("duration_ms")) for r in rows
                 if isinstance(r.detail, dict) and isinstance(r.detail.get("duration_ms"), (int, float))]
    return {
        "total": int(total), "offset": offset, "limit": limit,
        "failed_total": int(failed_total),
        "avg_duration_ms_page": round(sum(durations) / len(durations)) if durations else None,
        "runs": [{
            "id": r.id, "occurred_at": r.occurred_at.isoformat(), "actor": r.actor,
            "trigger": "n8n" if r.actor.startswith("workflow-") else "manuel",
            "action": r.action, "success": r.success, "error": r.error,
            "duration_ms": (r.detail or {}).get("duration_ms") if isinstance(r.detail, dict) else None,
            "detail": r.detail,
        } for r in rows],
    }


# ---------------------------------------------------------- IOC activity ---
@router.get("/iocs/{ioc_id}/activity")
def ioc_activity(ioc_id: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Everything that happened to one IOC: scores, publications, detections,
    enrichments and audit entries — the evidence file of the indicator."""
    ioc = db.get(Ioc, ioc_id)
    if ioc is None:
        raise HTTPException(status_code=404, detail="IOC introuvable")
    scores = db.execute(select(ScoreHistory).where(ScoreHistory.ioc_id == ioc_id)
                        .order_by(ScoreHistory.computed_at)).scalars().all()
    pubs = db.execute(select(Publication).where(Publication.ioc_id == ioc_id)
                      .order_by(Publication.published_at.desc())).scalars().all()
    dets = db.execute(select(Detection).where(Detection.ioc_id == ioc_id)
                      .order_by(Detection.matched_at.desc()).limit(100)).scalars().all()
    audit = db.execute(select(AuditLog).where(AuditLog.entity_id == str(ioc_id))
                       .order_by(AuditLog.id.desc()).limit(100)).scalars().all()
    sources = db.execute(select(IocSource).where(IocSource.ioc_id == ioc_id)).scalars().all()
    return {
        "ioc_id": str(ioc_id),
        "score_history": [{"score": s.score, "risk_level": s.risk_level.value if s.risk_level else None,
                           "policy": s.policy, "computed_at": s.computed_at.isoformat(),
                           "decision": (s.breakdown or {}).get("decision")} for s in scores],
        "publications": [{"id": str(p.id), "target": p.target, "target_ref": p.target_ref,
                          "status": p.status, "published_at": _iso(p.published_at),
                          "revoked_at": _iso(p.revoked_at), "detail": p.detail} for p in pubs],
        "detections": [_detection_out(d, ioc) for d in dets],
        "enrichments": [{"provider": e.provider, "verdict": e.verdict, "reputation": e.reputation,
                         "fetched_at": _iso(e.fetched_at), "is_synthetic": e.is_synthetic,
                         "error": (e.data or {}).get("error") if isinstance(e.data, dict) else None}
                        for e in sorted(ioc.enrichments, key=lambda e: e.fetched_at, reverse=True)],
        "provenance": [{"source": l.source.name, "provenance_group": l.source.provenance_group,
                        "reliability": l.source.reliability, "first_seen_at": _iso(l.first_seen_at),
                        "last_seen_at": _iso(l.last_seen_at), "external_id": l.external_id,
                        "external_url": l.external_url} for l in sources],
        "audit": [{"id": a.id, "occurred_at": a.occurred_at.isoformat(), "actor": a.actor,
                   "action": a.action, "success": a.success, "error": a.error, "detail": a.detail}
                  for a in audit],
    }


# --------------------------------------------------------------- search ----
@router.get("/search")
def global_search(q: str = Query(..., min_length=2, max_length=200),
                  db: Session = Depends(get_db), limit: int = Query(8, ge=1, le=25)) -> dict[str, Any]:
    """Topbar search: IOC values, sources and audit actors."""
    like = f"%{q}%"
    exact_first = case((Ioc.value == q, 0), else_=1)
    iocs = db.execute(select(Ioc).where(Ioc.value.ilike(like))
                      .order_by(exact_first, Ioc.score.desc().nulls_last()).limit(limit)).scalars().all()
    sources = db.execute(select(IntelSource).where(IntelSource.name.ilike(like)).limit(5)).scalars().all()
    return {
        "q": q,
        "iocs": [{"id": str(i.id), "value": i.value, "type": i.type.value, "status": i.status.value,
                  "score": i.score, "risk_level": i.risk_level.value if i.risk_level else None,
                  "is_synthetic": i.is_synthetic} for i in iocs],
        "sources": [{"name": s.name, "enabled": s.enabled} for s in sources],
    }
