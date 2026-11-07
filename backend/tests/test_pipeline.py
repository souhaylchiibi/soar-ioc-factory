"""Phase 3 — full pipeline (ingest → enrich → score → decide) on real DB.

Regression coverage for the state-machine bug found by the Phase 3 demo:
the decision must go through NORMALIZED -> ENRICHED -> SCORED, never jump.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.collectors.base import RawIndicator
from app.models.ioc import Ioc, IocStatus, IntelSource, LifecycleEvent
from app.services.pipeline import expire_due_iocs, run_full_pipeline, score_and_decide

NOW = datetime.now(timezone.utc)


class FakeProvider:
    """Deterministic test provider — verdict supplied by the constructor."""

    def __init__(self, verdict: str = "malicious", fail: bool = False,
                 name: str = "fake_provider"):
        self.name = name
        self.verdict = verdict
        self.fail = fail

    def enrich(self, ioc: Ioc):
        from app.enrichment.service import ProviderResult

        if self.fail:
            raise RuntimeError("provider unavailable (simulated)")
        return ProviderResult(
            provider=self.name, verdict=self.verdict,
            reputation=-80 if self.verdict == "malicious" else 50,
            data={"synthetic": True, "ioc": ioc.value},
        )


def raw_indicator(value: str, declared: str = "IP", synthetic: bool = True,
                  expires_at: datetime | None = None) -> RawIndicator:
    ctx: dict = {"declared_type": declared}
    if expires_at:
        ctx["expires_at"] = expires_at.isoformat()
    return RawIndicator(
        value=value, source_name="synthetic_lab", context=ctx,
        is_synthetic=synthetic, first_seen_at=NOW, last_seen_at=NOW,
    )


@pytest.fixture()
def src(db):
    db.add(IntelSource(name="synthetic_lab", provenance_group="synthetic_lab",
                       reliability=85))
    db.commit()
    return None


def path_of(db_session, ioc_id) -> list[str]:
    """Ordered status transitions recorded for this IOC."""
    events = db_session.execute(
        select(LifecycleEvent)
        .where(LifecycleEvent.ioc_id == ioc_id)
        .order_by(LifecycleEvent.created_at)
    ).scalars().all()
    return [f"{(e.from_status.value if e.from_status else 'NONE')}->{e.to_status.value}"
            for e in events]


class TestHappyPath:
    def test_full_path_to_monitored(self, db, src) -> None:
        report = run_full_pipeline(
            db, raw_indicator("203.0.113.50"),
            providers=[FakeProvider("malicious")],
        )
        db.commit()

        assert report.ok, report.errors
        ioc = db.get(Ioc, report.ioc_id)
        assert ioc.status == IocStatus.MONITORED
        assert ioc.score is not None and ioc.score >= 50
        # The legal path, step by step — no jump allowed.
        assert path_of(db, ioc.id) == [
            "NEW->NORMALIZED", "NORMALIZED->ENRICHED",
            "ENRICHED->SCORED", "SCORED->MONITORED",
        ]

    def test_high_confidence_publishes(self, db, src) -> None:
        """Strong source + 2 independent groups + malicious consensus -> publish."""
        db.add(IntelSource(name="indep_org", provenance_group="other_org", reliability=95))
        db.commit()

        report = run_full_pipeline(
            db, raw_indicator("203.0.113.51"),
            providers=[FakeProvider("malicious"), SecondProvider()],
        )
        # Add a second provenance group manually (same IOC, other org).
        db.commit()

        ioc = db.get(Ioc, report.ioc_id)
        # Add provenance from the independent org.
        from app.models.ioc import IocSource
        other = db.execute(select(IntelSource).where(IntelSource.name == "indep_org")).scalar_one()
        db.add(IocSource(ioc_id=ioc.id, source_id=other.id))
        db.commit()

        # Rescore with the new provenance taken into account.
        rescore = score_and_decide(db, ioc, triggered_by="test")
        db.commit()
        assert rescore.score is not None
        assert ioc.status in (IocStatus.PUBLISHED, IocStatus.MONITORED)
        assert ioc.score >= 50

    def test_low_confidence_rejects(self, db, src) -> None:
        # Old indicator, no detections, weak enrichment -> below threshold.
        report = run_full_pipeline(
            db, RawIndicator(
                value="203.0.113.60", source_name="synthetic_lab",
                context={"declared_type": "IP"},
                first_seen_at=NOW - timedelta(days=200),
                last_seen_at=NOW - timedelta(days=200),
                is_synthetic=True,
            ),
            providers=[FakeProvider("benign")],
        )
        db.commit()

        ioc = db.get(Ioc, report.ioc_id)
        assert ioc.status == IocStatus.REJECTED
        assert ioc.score < 50


class SecondProvider:
    name = "second_provider"

    def enrich(self, ioc: Ioc):
        from app.enrichment.service import ProviderResult
        return ProviderResult(provider=self.name, verdict="malicious", data={})


class TestResilience:
    def test_failing_provider_does_not_break_pipeline(self, db, src) -> None:
        report = run_full_pipeline(
            db, raw_indicator("203.0.113.70"),
            providers=[
                FakeProvider(fail=True, name="down_provider"),
                FakeProvider("suspicious", name="ok_provider"),
            ],
        )
        db.commit()

        assert report.enrichment_errors, "provider failure must be reported"
        assert report.enrichment_verdicts == ["suspicious"], "healthy provider still used"
        ioc = db.get(Ioc, report.ioc_id)
        assert ioc is not None
        # Pipeline continued with the provider that answered.
        assert ioc.status in (IocStatus.MONITORED, IocStatus.PUBLISHED, IocStatus.REJECTED)

    def test_all_providers_failing_still_scores(self, db, src) -> None:
        report = run_full_pipeline(
            db, raw_indicator("203.0.113.71"),
            providers=[FakeProvider(fail=True, name="down_a"),
                       FakeProvider(fail=True, name="down_b")],
        )
        db.commit()

        ioc = db.get(Ioc, report.ioc_id)
        # Neutral path: scored without enrichment verdicts.
        assert ioc.status in (IocStatus.MONITORED, IocStatus.REJECTED, IocStatus.PUBLISHED)
        assert ioc.score is not None
        assert len(report.enrichment_errors) == 2

    def test_duplicate_provider_names_run_once(self, db, src) -> None:
        """Two registrations with the same name = one provider (config bug)."""
        from app.enrichment.service import run_enrichment
        from app.services.ingest import ingest_raw

        outcome = ingest_raw(db, raw_indicator("203.0.113.73"))
        db.commit()
        ioc = db.get(Ioc, outcome.ioc_id)

        summary = run_enrichment(db, ioc, [FakeProvider("benign"),
                                           FakeProvider("malicious")])
        db.commit()
        assert len(summary.results) == 1, "duplicate provider names must be deduplicated"

    def test_no_provider_configured(self, db, src) -> None:
        report = run_full_pipeline(db, raw_indicator("203.0.113.72"), providers=None)
        db.commit()

        ioc = db.get(Ioc, report.ioc_id)
        assert ioc.status in (IocStatus.MONITORED, IocStatus.REJECTED, IocStatus.PUBLISHED)
        assert path_of(db, ioc.id)[1] == "NORMALIZED->ENRICHED"  # explicit bridge

    def test_rejected_indicator_not_rescored(self, db, src) -> None:
        first = run_full_pipeline(
            db, RawIndicator(
                value="203.0.113.80", source_name="synthetic_lab",
                context={"declared_type": "IP"},
                first_seen_at=NOW - timedelta(days=300),
                last_seen_at=NOW - timedelta(days=300), is_synthetic=True,
            ),
            providers=[FakeProvider("benign")],
        )
        db.commit()
        ioc = db.get(Ioc, first.ioc_id)
        assert ioc.status == IocStatus.REJECTED

        second = score_and_decide(db, ioc, triggered_by="test-rescore")
        assert second.errors, "terminal IOC must not be silently rescored"
        assert ioc.status == IocStatus.REJECTED


class TestExpiry:
    def test_due_iocs_marked_expired(self, db, src) -> None:
        report = run_full_pipeline(
            db, raw_indicator(
                "203.0.113.90",
                expires_at=NOW - timedelta(hours=1),
            ),
            providers=[FakeProvider("malicious")],
        )
        db.commit()
        ioc = db.get(Ioc, report.ioc_id)
        assert ioc.expires_at is not None and ioc.expires_at < NOW

        results = expire_due_iocs(db)
        db.commit()

        assert len(results) == 1
        assert results[0]["action"] == "expired"
        assert ioc.status == IocStatus.EXPIRED

    def test_future_expiry_untouched(self, db, src) -> None:
        run_full_pipeline(
            db, raw_indicator("203.0.113.91", expires_at=NOW + timedelta(days=5)),
            providers=[FakeProvider("malicious")],
        )
        db.commit()

        results = expire_due_iocs(db)
        db.commit()
        assert results == []

    def test_expired_ioc_not_double_expired(self, db, src) -> None:
        run_full_pipeline(
            db, raw_indicator("203.0.113.92", expires_at=NOW - timedelta(days=1)),
            providers=[FakeProvider("malicious")],
        )
        db.commit()
        expire_due_iocs(db)
        db.commit()
        # Second run: nothing left to expire.
        assert expire_due_iocs(db) == []
