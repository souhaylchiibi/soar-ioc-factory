"""IOC lifecycle state machine.

Every transition is validated here and recorded in `lifecycle_events`.
The rules mirror docs/ARCHITECTURE.md §2.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.models.ioc import Ioc, IocStatus, LifecycleEvent, RiskLevel

# Allowed transitions: from_status -> frozenset(to_status)
TRANSITIONS: dict[IocStatus, frozenset[IocStatus]] = {
    IocStatus.NEW: frozenset(
        {IocStatus.NORMALIZED, IocStatus.DUPLICATE, IocStatus.REJECTED}
    ),
    IocStatus.NORMALIZED: frozenset(
        {IocStatus.ENRICHED, IocStatus.REVIEW_REQUIRED, IocStatus.REJECTED}
    ),
    IocStatus.ENRICHED: frozenset({IocStatus.SCORED}),
    IocStatus.SCORED: frozenset(
        {
            IocStatus.PUBLISHED,       # score >= publish threshold
            IocStatus.MONITORED,       # between thresholds
            IocStatus.REJECTED,        # below monitor threshold
            IocStatus.REVIEW_REQUIRED, # ambiguous
            IocStatus.EXPIRED,         # already past its expiry
        }
    ),
    IocStatus.PUBLISHED: frozenset(
        {IocStatus.MONITORED, IocStatus.EXPIRED}
    ),
    IocStatus.MONITORED: frozenset(
        {IocStatus.EXPIRED, IocStatus.REVIEW_REQUIRED, IocStatus.PUBLISHED}
    ),
    IocStatus.REVIEW_REQUIRED: frozenset(
        {IocStatus.PUBLISHED, IocStatus.REJECTED, IocStatus.MONITORED}
    ),
    IocStatus.EXPIRED: frozenset({IocStatus.REMOVED}),
    IocStatus.REMOVED: frozenset(),
    IocStatus.REJECTED: frozenset(),
    IocStatus.DUPLICATE: frozenset(),
}

# Statuses that are "at rest" (terminal or awaiting human review).
TERMINAL_STATUSES = frozenset(
    {IocStatus.REMOVED, IocStatus.REJECTED, IocStatus.DUPLICATE}
)


class LifecycleError(RuntimeError):
    """Illegal transition or violated lifecycle invariant."""


@dataclass
class TransitionResult:
    from_status: IocStatus
    to_status: IocStatus
    event: LifecycleEvent


def can_transition(from_status: IocStatus, to_status: IocStatus) -> bool:
    return to_status in TRANSITIONS.get(from_status, frozenset())


def transition(
    ioc: Ioc,
    to_status: IocStatus,
    reason: str,
    actor: str = "system",
    triggered_by: str | None = None,
    verified: bool = False,
    verification_detail: dict | None = None,
) -> TransitionResult:
    """Apply a transition to `ioc` (in memory) and build its audit event.

    The caller owns the transaction: this function never commits.
    """
    if not reason or not reason.strip():
        raise LifecycleError("a transition requires a non-empty reason")

    from_status = ioc.status
    if from_status == to_status:
        raise LifecycleError(f"IOC already in status {to_status.value}")

    if not can_transition(from_status, to_status):
        allowed = ", ".join(sorted(s.value for s in TRANSITIONS.get(from_status, frozenset())) or ["<none>"])
        raise LifecycleError(
            f"illegal transition {from_status.value} -> {to_status.value} (allowed: {allowed})"
        )

    score_before = ioc.score

    # Side effects carried by the status itself.
    now = datetime.now(timezone.utc)
    if to_status == IocStatus.REMOVED:
        ioc.removed_at = now
    if to_status == IocStatus.EXPIRED and ioc.expires_at is None:
        # An expiry event without a date is a data bug — refuse to fabricate one.
        raise LifecycleError("cannot EXPIRE an indicator without expires_at")

    ioc.status = to_status

    # Risk level follows the score once known; keep it coherent.
    if ioc.score is not None and to_status in (
        IocStatus.SCORED,
        IocStatus.PUBLISHED,
        IocStatus.MONITORED,
        IocStatus.REJECTED,
    ):
        ioc.risk_level = risk_level_for(ioc.score)

    event = LifecycleEvent(
        ioc_id=ioc.id,
        from_status=from_status,
        to_status=to_status,
        reason=reason.strip(),
        actor=actor,
        triggered_by=triggered_by,
        score_before=score_before,
        score_after=ioc.score,
        verified=verified,
        verification_detail=verification_detail,
    )
    return TransitionResult(from_status=from_status, to_status=to_status, event=event)


def risk_level_for(score: int) -> RiskLevel:
    if score >= 80:
        return RiskLevel.CRITICAL
    if score >= 65:
        return RiskLevel.HIGH
    if score >= 50:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW
