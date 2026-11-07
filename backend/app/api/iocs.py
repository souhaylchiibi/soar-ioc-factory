"""IOC API — the surface consumed by the dashboard and by n8n workflows."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.collectors.base import RawIndicator
from app.core.db import get_db
from app.core.logging import get_logger
from app.lifecycle.machine import LifecycleError, transition
from app.models.ioc import (
    AuditLog,
    Ioc,
    IocSource,
    IocStatus,
    IntelSource,
    LifecycleEvent,
    ScoreHistory,
)
from app.schemas.ioc import (
    DashboardStats,
    IocDetail,
    IocListResponse,
    IocOut,
    IngestRequest,
    IngestResponse,
    IngestResult,
    LifecycleEventOut,
    ScoringRunRequest,
    ScoringRunResponse,
    SourceLinkOut,
    SourceStat,
    TransitionRequest,
)
from app.services.pipeline import run_full_pipeline, score_and_decide
from app.services.ingest import ingest_raw

logger = get_logger("soar.api.iocs")
router = APIRouter(prefix="/iocs", tags=["iocs"])


# ------------------------------------------------------------------ ingest --
@router.post("/ingest", response_model=IngestResponse)
def ingest(body: IngestRequest, db: Session = Depends(get_db)) -> IngestResponse:
    """Stage 1-2 of the factory: normalize + deduplicate a batch."""
    results: list[IngestResult] = []
    # Key must match IngestResponse field names (duplicates, not duplicate).
    counts = {"created": 0, "updated": 0, "duplicates": 0, "rejected": 0}

    for item in body.items:
        raw = RawIndicator(
            value=item.value,
            source_name=item.source,
            external_id=item.external_id,
            external_url=item.external_url,
            first_seen_at=item.first_seen_at,
            last_seen_at=item.last_seen_at,
            tags=item.tags,
            context={"declared_type": item.type.value if item.type else None,
                     "expires_at": item.expires_at.isoformat() if item.expires_at else None},
            is_synthetic=item.is_synthetic,
        )
        raw.context = {k: v for k, v in raw.context.items() if v is not None}
        outcome = ingest_raw(db, raw, actor="api")
        key = "duplicates" if outcome.action == "duplicate" else outcome.action
        counts[key] = counts.get(key, 0) + 1
        results.append(IngestResult(
            raw_value=outcome.raw_value, action=outcome.action,
            ioc_id=outcome.ioc_id, reason=outcome.reason,
        ))

    db.commit()
    return IngestResponse(**counts, results=results)


# ------------------------------------------------------------------- read ---
def _ioc_filters(status: Optional[IocStatus], ioc_type: Optional[str], q: Optional[str],
                 synthetic: Optional[bool]):
    clauses = []
    if status is not None:
        clauses.append(Ioc.status == status)
    if ioc_type:
        clauses.append(Ioc.type == ioc_type)
    if q:
        clauses.append(Ioc.value.ilike(f"%{q}%"))
    if synthetic is not None:
        clauses.append(Ioc.is_synthetic.is_(synthetic))
    return clauses


@router.get("", response_model=IocListResponse)
def list_iocs(
    db: Session = Depends(get_db),
    status: Optional[IocStatus] = None,
    type: Optional[str] = Query(None, pattern="^(IP|DOMAIN|URL|HASH_MD5|HASH_SHA1|HASH_SHA256)$"),
    q: Optional[str] = Query(None, max_length=200),
    synthetic: Optional[bool] = None,
    sort: str = Query("last_seen_desc", pattern="^(last_seen_desc|score_desc|score_asc|expires_asc)$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> IocListResponse:
    clauses = _ioc_filters(status, type, q, synthetic)

    total = db.execute(select(func.count(Ioc.id)).where(*clauses)).scalar() or 0

    order = {
        "last_seen_desc": Ioc.last_seen_at.desc(),
        "score_desc": Ioc.score.desc().nulls_last(),
        "score_asc": Ioc.score.asc().nulls_last(),
        "expires_asc": Ioc.expires_at.asc().nulls_last(),
    }[sort]

    rows = db.execute(
        select(Ioc).where(*clauses).order_by(order).offset(offset).limit(limit)
    ).scalars().all()

    items = []
    for ioc in rows:
        out = IocOut.model_validate(ioc)
        out.independent_source_count = _independent_count(db, ioc.id)
        items.append(out)

    return IocListResponse(total=total, offset=offset, limit=limit, items=items)


def _independent_count(db: Session, ioc_id) -> int:
    return int(db.execute(
        select(func.count(func.distinct(IntelSource.provenance_group)))
        .select_from(IocSource)
        .join(IntelSource, IntelSource.id == IocSource.source_id)
        .where(IocSource.ioc_id == ioc_id)
    ).scalar() or 0)


@router.get("/{ioc_id}", response_model=IocDetail)
def get_ioc(ioc_id: uuid.UUID, db: Session = Depends(get_db)) -> IocDetail:
    ioc = db.get(Ioc, ioc_id)
    if ioc is None:
        raise HTTPException(status_code=404, detail="IOC introuvable")

    detail = IocDetail.model_validate(ioc)
    detail.independent_source_count = _independent_count(db, ioc.id)
    detail.sources = [
        SourceLinkOut(
            name=l.source.name, provenance_group=l.source.provenance_group,
            reliability=l.source.reliability, external_id=l.external_id,
        )
        for l in ioc.source_links
    ]
    detail.lifecycle = [LifecycleEventOut.model_validate(e) for e in ioc.lifecycle_events]
    detail.enrichment_verdicts = [e.verdict for e in ioc.enrichments if e.verdict]
    if ioc.score_breakdown:
        detail.score = ioc.score_breakdown.get("final_score", ioc.score)
    return detail


# ----------------------------------------------------------------- actions --
@router.post("/{ioc_id}/transition", response_model=LifecycleEventOut)
def manual_transition(ioc_id: uuid.UUID, body: TransitionRequest, db: Session = Depends(get_db)) -> LifecycleEventOut:
    """Manual lifecycle change (analyst/admin action, always audited)."""
    ioc = db.get(Ioc, ioc_id)
    if ioc is None:
        raise HTTPException(status_code=404, detail="IOC introuvable")
    try:
        result = transition(
            ioc, body.to_status, reason=body.reason,
            actor=body.actor, triggered_by="manual-api",
            verified=body.verified,
        )
    except LifecycleError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    db.add(result.event)
    db.add(AuditLog(
        actor=body.actor, action="TRANSITION", entity_type="ioc", entity_id=str(ioc.id),
        detail={"from": result.from_status.value, "to": result.to_status.value,
                "reason": body.reason},
    ))
    db.commit()
    return LifecycleEventOut.model_validate(result.event)


@router.post("/scoring/run", response_model=ScoringRunResponse)
def run_scoring(body: ScoringRunRequest, db: Session = Depends(get_db)) -> ScoringRunResponse:
    """Batch scoring — called by n8n workflow 4."""
    clauses = []
    if body.ioc_ids:
        clauses.append(Ioc.id.in_(body.ioc_ids))
    elif body.only_status is not None:
        clauses.append(Ioc.status == body.only_status)

    targets = db.execute(select(Ioc).where(*clauses).limit(500)).scalars().all()

    resp = ScoringRunResponse()
    for ioc in targets:
        report = score_and_decide(db, ioc, triggered_by="workflow-4")
        if report.score is None:
            continue
        resp.scored += 1
        if report.decision == "publish":
            resp.published += 1
        elif report.decision == "monitor":
            resp.monitored += 1
        elif report.decision == "reject":
            resp.rejected += 1
        resp.details.append({
            "ioc_id": str(ioc.id), "value": ioc.value, "score": report.score,
            "decision": report.decision, "explanation": report.score_explanation,
        })
    db.commit()
    return resp


# --------------------------------------------------------------- statistics -
@router.get("/stats/dashboard", response_model=DashboardStats, tags=["stats"])
def dashboard_stats(db: Session = Depends(get_db)) -> DashboardStats:
    """Every number here comes from the database — never fabricated."""

    def count(*clauses) -> int:
        return int(db.execute(select(func.count(Ioc.id)).where(*clauses)).scalar() or 0)

    active_statuses = [IocStatus.PUBLISHED, IocStatus.MONITORED, IocStatus.SCORED,
                       IocStatus.NEW, IocStatus.NORMALIZED, IocStatus.ENRICHED,
                       IocStatus.REVIEW_REQUIRED]

    # by_type / by_status / by_risk
    by_type = {r[0].value: r[1] for r in db.execute(
        select(Ioc.type, func.count(Ioc.id)).group_by(Ioc.type)).all()}
    by_status = {r[0].value: r[1] for r in db.execute(
        select(Ioc.status, func.count(Ioc.id)).group_by(Ioc.status)).all()}
    by_risk = {r[0].value: r[1] for r in db.execute(
        select(Ioc.risk_level, func.count(Ioc.id)).where(Ioc.risk_level.is_not(None)).group_by(Ioc.risk_level)).all()}

    # score distribution (buckets)
    buckets = {"0-49": 0, "50-64": 0, "65-79": 0, "80-89": 0, "90-100": 0}
    for score, n in db.execute(
        select(Ioc.score, func.count(Ioc.id)).where(Ioc.score.is_not(None)).group_by(Ioc.score)
    ).all():
        s = int(score)
        key = "0-49" if s < 50 else "50-64" if s < 65 else "65-79" if s < 80 else "80-89" if s < 90 else "90-100"
        buckets[key] += n

    avg_score = db.execute(select(func.avg(Ioc.score))).scalar()

    # daily new IOCs (last 14 days)
    since = datetime.now(timezone.utc) - timedelta(days=14)
    daily = [
        {"date": r[0].isoformat(), "count": r[1]}
        for r in db.execute(
            select(func.date(Ioc.created_at), func.count(Ioc.id))
            .where(Ioc.created_at >= since)
            .group_by(func.date(Ioc.created_at))
            .order_by(func.date(Ioc.created_at))
        ).all()
    ]

    # dedup rate: raw items seen vs distinct IOCs (from audit trail)
    total_ingest = int(db.execute(
        select(func.count(AuditLog.id)).where(AuditLog.action.in_(["NORMALIZE", "DEDUP"]))
    ).scalar() or 0)
    dedup_events = int(db.execute(
        select(func.count(AuditLog.id)).where(AuditLog.action == "DEDUP")
    ).scalar() or 0)
    dedup_rate = round(dedup_events / total_ingest, 4) if total_ingest else None

    # avg processing time: ingest -> scored (seconds)
    avg_proc = db.execute(
        select(func.avg(func.extract(
            "epoch",
            (select(ScoreHistory.computed_at).where(ScoreHistory.ioc_id == Ioc.id)
             .correlate(Ioc).order_by(ScoreHistory.computed_at).limit(1).scalar_subquery())
            - Ioc.created_at
        ))).where(Ioc.score.is_not(None))
    ).scalar()

    total_detections = int(db.execute(select(func.coalesce(func.sum(Ioc.detection_count), 0))).scalar() or 0)
    false_positives = int(db.execute(select(func.coalesce(func.sum(Ioc.false_positive_count), 0))).scalar() or 0)

    return DashboardStats(
        total_iocs=count(),
        active_iocs=count(Ioc.status.in_(active_statuses)),
        expired_iocs=count(Ioc.status == IocStatus.EXPIRED),
        rejected_iocs=count(Ioc.status == IocStatus.REJECTED),
        removed_iocs=count(Ioc.status == IocStatus.REMOVED),
        review_required=count(Ioc.status == IocStatus.REVIEW_REQUIRED),
        published_iocs=count(Ioc.status == IocStatus.PUBLISHED),
        monitored_iocs=count(Ioc.status == IocStatus.MONITORED),
        duplicates_seen=count(Ioc.duplicate_of.is_not(None)),
        synthetic_iocs=count(Ioc.is_synthetic.is_(True)),
        false_positives=false_positives,
        total_detections=total_detections,
        avg_score=round(float(avg_score), 1) if avg_score is not None else None,
        avg_processing_seconds=round(float(avg_proc), 1) if avg_proc is not None else None,
        dedup_rate=dedup_rate,
        by_type=by_type,
        by_status=by_status,
        by_risk=by_risk,
        score_distribution=buckets,
        daily_new=daily,
    )


@router.get("/stats/sources", response_model=list[SourceStat], tags=["stats"])
def source_stats(db: Session = Depends(get_db)) -> list[SourceStat]:
    out = []
    for src in db.execute(select(IntelSource)).scalars().all():
        n = db.execute(
            select(func.count(Ioc.id)).select_from(IocSource)
            .where(IocSource.source_id == src.id)
        ).scalar() or 0
        out.append(SourceStat(
            name=src.name, provenance_group=src.provenance_group,
            reliability=src.reliability, enabled=src.enabled,
            ioc_count=int(n), last_success_at=src.last_success_at,
            last_error=src.last_error,
        ))
    return out


# ---------------------------------------------------------------- lifecycle -
@router.get("/lifecycle/events", response_model=list[LifecycleEventOut], tags=["lifecycle"])
def lifecycle_events(
    db: Session = Depends(get_db),
    ioc_id: Optional[uuid.UUID] = None,
    limit: int = Query(100, ge=1, le=500),
) -> list[LifecycleEventOut]:
    stmt = select(LifecycleEvent).order_by(LifecycleEvent.created_at.desc()).limit(limit)
    if ioc_id:
        stmt = stmt.where(LifecycleEvent.ioc_id == ioc_id)
    return [LifecycleEventOut.model_validate(e) for e in db.execute(stmt).scalars().all()]
