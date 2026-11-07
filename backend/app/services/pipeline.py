"""End-to-end pipeline: ingest → enrich → score → decide → transition.

This is the heart of the "factory": one call takes a raw indicator to a
decision, recording every step. Used by the REST API and by the n8n
workflows (each stage can also be called separately).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.collectors.base import RawIndicator
from app.core.config import settings
from app.core.logging import get_logger
from app.enrichment.service import run_enrichment
from app.lifecycle.machine import IocStatus, transition
from app.models.ioc import (
    AuditLog,
    Ioc,
    IocSource,
    IntelSource,
    LifecycleEvent,
    ScoreHistory,
)
from app.scoring.engine import ScoringInput, compute_score
from app.services.ingest import IngestOutcome, ingest_raw

logger = get_logger("soar.pipeline")


@dataclass
class StageReport:
    """Trace of one pipeline run — used by workflows, API and tests."""

    ioc_id: str
    ingest: Optional[IngestOutcome] = None
    enrichment_verdicts: list[str] = field(default_factory=list)
    enrichment_errors: list[str] = field(default_factory=list)
    score: Optional[int] = None
    decision: Optional[str] = None
    score_explanation: str = ""
    transitions: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _independent_source_count(db: Session, ioc_id) -> int:
    """Count DISTINCT provenance groups (anti-collusion), not raw feeds."""
    row = db.execute(
        select(func.count(func.distinct(IntelSource.provenance_group)))
        .select_from(IocSource)
        .join(IntelSource, IntelSource.id == IocSource.source_id)
        .where(IocSource.ioc_id == ioc_id)
    ).scalar()
    return int(row or 0)


def _best_reliability(db: Session, ioc_id) -> int:
    row = db.execute(
        select(func.coalesce(func.max(IntelSource.reliability), 50))
        .select_from(IocSource)
        .join(IntelSource, IntelSource.id == IocSource.source_id)
        .where(IocSource.ioc_id == ioc_id)
    ).scalar()
    return int(row or 50)


def score_and_decide(
    db: Session,
    ioc: Ioc,
    actor: str = "scoring_worker",
    triggered_by: str | None = None,
) -> StageReport:
    """Compute the score, persist it, and apply the policy decision."""
    report = StageReport(ioc_id=str(ioc.id))

    # Nothing to score if the indicator is already at rest.
    if ioc.status in (IocStatus.REMOVED, IocStatus.REJECTED, IocStatus.DUPLICATE, IocStatus.EXPIRED):
        report.errors.append(f"IOC in terminal status {ioc.status.value}: not scored")
        return report

    verdicts = [e.verdict for e in ioc.enrichments if e.verdict]

    inp = ScoringInput(
        ioc_type=ioc.type,
        first_seen_at=ioc.first_seen_at,
        last_seen_at=ioc.last_seen_at,
        source_reliability=_best_reliability(db, ioc.id),
        independent_source_count=_independent_source_count(db, ioc.id),
        enrichment_verdicts=verdicts,
        detection_count=ioc.detection_count,
        false_positive_count=ioc.false_positive_count,
        policy=_active_policy_params(db),
    )
    result = compute_score(inp)

    ioc.score = result.score
    ioc.score_breakdown = result.breakdown
    ioc.scored_at = datetime.now(timezone.utc)

    db.add(ScoreHistory(
        ioc_id=ioc.id,
        score=result.score,
        risk_level=ioc.risk_level,
        breakdown=result.breakdown,
        policy=result.policy_version,
    ))

    report.score = result.score
    report.decision = result.decision
    report.score_explanation = result.explanation
    report.enrichment_verdicts = verdicts

    # ---- Drive the state machine to SCORED, then apply the decision ----
    # The legal path is NORMALIZED -> ENRICHED -> SCORED -> <decision>.
    # Each step is explicit: skipping one would be an illegal transition.
    try:
        if ioc.status == IocStatus.NORMALIZED:
            tr = transition(
                ioc, IocStatus.ENRICHED,
                reason="scoring requested — marking enrichment stage complete",
                actor=actor, triggered_by=triggered_by,
            )
            db.add(tr.event)
            report.transitions.append({"to": "ENRICHED", "reason": tr.event.reason})

        if ioc.status == IocStatus.ENRICHED:
            tr = transition(
                ioc, IocStatus.SCORED,
                reason=f"score {result.score}/100 computed ({result.policy_version})",
                actor=actor, triggered_by=triggered_by,
            )
            db.add(tr.event)
            report.transitions.append({"to": "SCORED", "reason": tr.event.reason})
    except Exception as exc:
        report.errors.append(str(exc))
        db.add(AuditLog(
            actor=actor, action="SCORE", entity_type="ioc", entity_id=str(ioc.id),
            detail={"stage_error": str(exc), "score": result.score}, success=False, error=str(exc),
        ))
        return report

    # ---- Policy decision (from SCORED) ---------------------------------
    target = {
        "publish": IocStatus.PUBLISHED,
        "monitor": IocStatus.MONITORED,
        "reject": IocStatus.REJECTED,
    }[result.decision]

    # An indicator already PUBLISHED that stays "publish": score refreshed only.
    if ioc.status == IocStatus.PUBLISHED and target == IocStatus.PUBLISHED:
        report.transitions.append({"to": "PUBLISHED", "note": "already published, score refreshed"})
        return report
    if ioc.status == target:
        # Rescoring confirmed the current state — no transition needed.
        report.transitions.append({"to": target.value, "note": "score refreshed, state unchanged"})
        return report
    if ioc.status in (IocStatus.PUBLISHED, IocStatus.MONITORED) and target == IocStatus.REJECTED:
        # Step down requires REVIEW first (never silently unpublish).
        target = IocStatus.REVIEW_REQUIRED

    try:
        tr = transition(
            ioc,
            target,
            reason=f"score {result.score}/100 -> {result.decision} ({result.policy_version})",
            actor=actor,
            triggered_by=triggered_by,
        )
        db.add(tr.event)
        report.transitions.append({"to": target.value, "reason": tr.event.reason})
    except Exception as exc:  # illegal transition: keep the score, log it
        report.errors.append(str(exc))
        logger.warning("transition refused", extra={"ioc_id": str(ioc.id), "action": "TRANSITION"})

    db.add(AuditLog(
        actor=actor, action="SCORE", entity_type="ioc", entity_id=str(ioc.id),
        detail={"score": result.score, "decision": result.decision,
                "policy": result.policy_version, "explanation": result.explanation},
    ))
    return report


def run_full_pipeline(
    db: Session,
    raw: RawIndicator,
    providers: list[Any] | None = None,
    actor: str = "pipeline",
    triggered_by: str | None = None,
    enrich: bool = True,
    score: bool = True,
) -> StageReport:
    """Ingest one raw indicator and drive it as far as configured."""
    outcome = ingest_raw(db, raw, actor=actor)
    report = StageReport(ioc_id=outcome.ioc_id or "")
    report.ingest = outcome

    if not outcome.ok or outcome.ioc_id is None:
        report.errors.append(outcome.reason)
        return report

    ioc = db.get(Ioc, outcome.ioc_id)
    if ioc is None:  # pragma: no cover - defensive
        report.errors.append("IOC vanished after ingest")
        return report

    # ---- Enrichment -----------------------------------------------------
    if enrich and providers:
        try:
            summary = run_enrichment(db, ioc, providers)
            report.enrichment_verdicts = summary.verdicts
            report.enrichment_errors = [f"{e.provider}: {e.error}" for e in summary.errors]
            if summary.verdicts and ioc.status == IocStatus.NORMALIZED:
                tr = transition(
                    ioc, IocStatus.ENRICHED,
                    reason=f"{len(summary.verdicts)} provider(s): {', '.join(summary.verdicts)}",
                    actor=actor, triggered_by=triggered_by,
                )
                db.add(tr.event)
                report.transitions.append({"to": "ENRICHED", "reason": tr.event.reason})
        except Exception as exc:
            report.errors.append(f"enrichment failed: {exc}")

    # ---- Scoring + decision --------------------------------------------
    if score and ioc.status in (IocStatus.ENRICHED, IocStatus.SCORED, IocStatus.NORMALIZED):
        # Bridge: scoring is legal from ENRICHED only. When no verdict was
        # obtained (no provider, or every provider failed) we still record an
        # explicit ENRICHED step — the indicator is scored WITHOUT enrichment
        # evidence, and the reason says so (nothing is invented).
        if ioc.status == IocStatus.NORMALIZED:
            reason = (
                "enrichment stage complete — verdicts: "
                + (", ".join(report.enrichment_verdicts) if report.enrichment_verdicts
                   else "none (providers unavailable or not configured)")
            )
            tr = transition(
                ioc, IocStatus.ENRICHED, reason=reason,
                actor=actor, triggered_by=triggered_by,
            )
            db.add(tr.event)
            report.transitions.append({"to": "ENRICHED", "reason": tr.event.reason})

        if ioc.status == IocStatus.ENRICHED:
            score_report = score_and_decide(db, ioc, actor=actor, triggered_by=triggered_by)
            report.score = score_report.score
            report.decision = score_report.decision
            report.score_explanation = score_report.score_explanation
            report.transitions.extend(score_report.transitions)
            report.errors.extend(score_report.errors)

    db.flush()
    return report


def _active_policy_params(db: Session) -> dict:
    from app.models.ioc import ScoringPolicy
    from app.scoring.engine import DEFAULT_POLICY

    row = db.execute(
        select(ScoringPolicy).where(ScoringPolicy.active.is_(True)).limit(1)
    ).scalar_one_or_none()
    return row.params if row is not None else dict(DEFAULT_POLICY)


def expire_due_iocs(db: Session, actor: str = "expiry_worker") -> list[dict[str, Any]]:
    """Find IOCs past their expiry, transition EXPIRED, report them.

    Removal (REMOVED) happens only after the publication target confirms it —
    see integrations: never mark REMOVED without verification.
    """
    now = datetime.now(timezone.utc)
    due = db.execute(
        select(Ioc).where(
            Ioc.expires_at.is_not(None),
            Ioc.expires_at < now,
            Ioc.status.notin_([IocStatus.EXPIRED, IocStatus.REMOVED, IocStatus.REJECTED, IocStatus.DUPLICATE]),
        )
    ).scalars().all()

    results = []
    for ioc in due:
        try:
            tr = transition(
                ioc, IocStatus.EXPIRED,
                reason=f"expires_at={ioc.expires_at.isoformat()} dépassé à {now.isoformat()}",
                actor=actor, triggered_by="workflow-7",
            )
            db.add(tr.event)
            db.add(AuditLog(
                actor=actor, action="EXPIRE", entity_type="ioc", entity_id=str(ioc.id),
                detail={"value": ioc.value, "expired_at": ioc.expires_at.isoformat()},
            ))
            results.append({"ioc_id": str(ioc.id), "value": ioc.value, "action": "expired"})
        except Exception as exc:
            results.append({"ioc_id": str(ioc.id), "action": "error", "error": str(exc)})
    db.flush()
    return results
