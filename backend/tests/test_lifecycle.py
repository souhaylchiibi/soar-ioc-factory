"""Phase 3 — lifecycle state machine: legal/illegal transitions, audit trail."""
from datetime import datetime, timedelta, timezone

import pytest

from app.lifecycle.machine import (
    TRANSITIONS,
    LifecycleError,
    can_transition,
    risk_level_for,
    transition,
)
from app.models.ioc import Ioc, IocStatus, IocType


def make_ioc(status: IocStatus = IocStatus.NEW, score: int | None = None,
             expires_at: datetime | None = None) -> Ioc:
    return Ioc(
        type=IocType.IP,
        value="203.0.113.1",
        raw_value="203.0.113.1",
        status=status,
        fingerprint="f" * 64,
        score=score,
        expires_at=expires_at,
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
    )


class TestHappyPath:
    def test_full_forward_journey(self) -> None:
        """NEW -> NORMALIZED -> ENRICHED -> SCORED -> PUBLISHED -> MONITORED -> EXPIRED -> REMOVED."""
        ioc = make_ioc(score=85,
                       expires_at=datetime.now(timezone.utc) + timedelta(days=1))
        path = [
            (IocStatus.NORMALIZED, "validated"),
            (IocStatus.ENRICHED, "enriched"),
            (IocStatus.SCORED, "scored 85"),
            (IocStatus.PUBLISHED, "score >= 80"),
            (IocStatus.MONITORED, "monitoring detections"),
            (IocStatus.EXPIRED, "past expiry"),
            (IocStatus.REMOVED, "removal verified on target"),
        ]
        for target, reason in path:
            result = transition(ioc, target, reason)
            assert result.from_status != target
            assert ioc.status == target

    def test_events_carry_actor_reason_and_scores(self) -> None:
        ioc = make_ioc(IocStatus.ENRICHED, score=None)
        transition(ioc, IocStatus.SCORED, "computed", actor="scoring_worker",
                   triggered_by="workflow-4")
        ioc.score = 85
        result = transition(ioc, IocStatus.PUBLISHED, "score 85 >= 80")
        event = result.event
        assert event.actor == "system"
        assert event.triggered_by is None
        assert event.to_status == IocStatus.PUBLISHED
        assert event.score_after == 85

    def test_removal_timestamp_set(self) -> None:
        ioc = make_ioc(IocStatus.EXPIRED,
                       expires_at=datetime.now(timezone.utc) - timedelta(hours=1))
        transition(ioc, IocStatus.REMOVED, "verified removal")
        assert ioc.removed_at is not None

    def test_risk_level_follows_score(self) -> None:
        ioc = make_ioc(IocStatus.ENRICHED)
        ioc.score = 85
        transition(ioc, IocStatus.SCORED, "scored")
        assert ioc.risk_level.value == "CRITICAL"

    @pytest.mark.parametrize("score,expected", [
        (0, "LOW"), (49, "LOW"), (50, "MEDIUM"), (64, "MEDIUM"),
        (65, "HIGH"), (79, "HIGH"), (80, "CRITICAL"), (100, "CRITICAL"),
    ])
    def test_risk_level_boundaries(self, score: int, expected: str) -> None:
        assert risk_level_for(score).value == expected


class TestIllegalTransitions:
    def test_cannot_skip_normalization(self) -> None:
        ioc = make_ioc(IocStatus.NEW)
        with pytest.raises(LifecycleError, match="illegal transition"):
            transition(ioc, IocStatus.PUBLISHED, "skip")

    def test_terminal_states_are_closed(self) -> None:
        for status in (IocStatus.REMOVED, IocStatus.REJECTED, IocStatus.DUPLICATE):
            assert TRANSITIONS[status] == frozenset()
            ioc = make_ioc(status)
            with pytest.raises(LifecycleError):
                transition(ioc, IocStatus.PUBLISHED, "back from the dead")

    def test_same_status_rejected(self) -> None:
        ioc = make_ioc(IocStatus.NEW)
        with pytest.raises(LifecycleError, match="already in status"):
            transition(ioc, IocStatus.NEW, "noop")

    def test_expiry_requires_a_date(self) -> None:
        """We never fabricate an expiry date to satisfy a transition."""
        ioc = make_ioc(IocStatus.MONITORED, expires_at=None)
        with pytest.raises(LifecycleError, match="without expires_at"):
            transition(ioc, IocStatus.EXPIRED, "should be impossible")

    def test_reason_is_mandatory(self) -> None:
        ioc = make_ioc(IocStatus.NEW)
        with pytest.raises(LifecycleError, match="reason"):
            transition(ioc, IocStatus.NORMALIZED, "   ")

    @pytest.mark.parametrize("frm,to", [
        (IocStatus.NEW, IocStatus.SCORED),
        (IocStatus.NEW, IocStatus.REMOVED),
        (IocStatus.ENRICHED, IocStatus.PUBLISHED),
        (IocStatus.EXPIRED, IocStatus.PUBLISHED),
    ])
    def test_known_bad_pairs(self, frm: IocStatus, to: IocStatus) -> None:
        assert not can_transition(frm, to)


class TestDocumentedRules:
    def test_scored_routes_by_decision(self) -> None:
        allowed = TRANSITIONS[IocStatus.SCORED]
        assert IocStatus.PUBLISHED in allowed
        assert IocStatus.MONITORED in allowed
        assert IocStatus.REJECTED in allowed

    def test_duplicate_branch_from_new_only(self) -> None:
        assert IocStatus.DUPLICATE in TRANSITIONS[IocStatus.NEW]
        assert all(IocStatus.DUPLICATE not in v for k, v in TRANSITIONS.items() if k != IocStatus.NEW)
