"""Phase 3 — ingestion pipeline against the real PostgreSQL schema.

Covers: creation, normalization, dedup, rejection, provenance, audit trail,
synthetic flagging and lifecycle recording.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, text

from app.collectors.base import RawIndicator
from app.models.ioc import (
    AuditLog,
    Ioc,
    IocSource,
    IocStatus,
    IntelSource,
    LifecycleEvent,
)
from app.services.ingest import ingest_raw

NOW = datetime.now(timezone.utc)


def raw(value: str, declared: str | None = None, source: str = "test_source",
        synthetic: bool = False, first_seen: datetime | None = None,
        tags: list[str] | None = None, ctx: dict | None = None) -> RawIndicator:
    context = dict(ctx or {})
    if declared:
        context["declared_type"] = declared
    return RawIndicator(
        value=value, source_name=source, is_synthetic=synthetic,
        first_seen_at=first_seen, last_seen_at=first_seen, tags=tags or [],
        context=context,
    )


@pytest.fixture()
def registered_source(db):
    src = IntelSource(name="test_source", provenance_group="test_group", reliability=70)
    other = IntelSource(name="echo_of_test", provenance_group="test_group", reliability=70)
    independent = IntelSource(name="other_org", provenance_group="other_org", reliability=90)
    db.add_all([src, other, independent])
    db.commit()
    return src


class TestCreation:
    def test_valid_ip_created_and_normalized(self, db, registered_source) -> None:
        outcome = ingest_raw(db, raw(" 203.0.113.9 ", declared="IP"))
        db.commit()

        assert outcome.action == "created"
        ioc = db.get(Ioc, outcome.ioc_id)
        assert ioc is not None
        assert ioc.value == "203.0.113.9"          # trimmed + canonical
        assert ioc.raw_value == "203.0.113.9"
        assert ioc.status == IocStatus.NORMALIZED   # NEW -> NORMALIZED automatic
        assert ioc.type.value == "IP"

    def test_lifecycle_event_recorded(self, db, registered_source) -> None:
        outcome = ingest_raw(db, raw("203.0.113.9", declared="IP"))
        db.commit()

        events = db.execute(
            select(LifecycleEvent).where(LifecycleEvent.ioc_id == outcome.ioc_id)
        ).scalars().all()
        assert len(events) == 1
        assert events[0].from_status == IocStatus.NEW
        assert events[0].to_status == IocStatus.NORMALIZED
        assert events[0].triggered_by == "ingest"
        assert events[0].reason

    def test_audit_row_written(self, db, registered_source) -> None:
        ingest_raw(db, raw("203.0.113.9", declared="IP"))
        db.commit()

        audits = db.execute(select(AuditLog)).scalars().all()
        assert audits, "audit trail must record ingestion"
        assert audits[0].action == "NORMALIZE"
        assert audits[0].success is True
        assert audits[0].detail["fingerprint"]

    def test_provenance_link_created(self, db, registered_source) -> None:
        outcome = ingest_raw(db, raw("203.0.113.9", declared="IP"))
        db.commit()

        link = db.execute(
            select(IocSource).where(IocSource.ioc_id == outcome.ioc_id)
        ).scalar_one()
        assert link.source_id == registered_source.id

    def test_six_types_accepted(self, db, registered_source) -> None:
        cases = [
            ("198.51.100.7", "IP"),
            ("evil.example", "DOMAIN"),
            ("http://evil.example/x", "URL"),
            ("44d88612fea8a8f36de82e1278abb02f", "HASH_MD5"),
            ("a94a8fe5ccb19ba61c4c0873d391e987982fbbd3", "HASH_SHA1"),
            ("9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08", "HASH_SHA256"),
        ]
        for value, declared in cases:
            outcome = ingest_raw(db, raw(value, declared=declared))
            assert outcome.action == "created", f"{value} -> {outcome.reason}"
        db.commit()
        assert db.execute(select(func.count(Ioc.id))).scalar() == 6


class TestRejection:
    @pytest.mark.parametrize("value,declared", [
        ("999.999.999.999", "IP"),
        ("not a domain!!", "DOMAIN"),
        ("ftp://x.example/a", "URL"),
        ("zzzz8612fea8a8f36de82e1278abb02f", "HASH_MD5"),
        ("", "IP"),
    ])
    def test_invalid_values_rejected_not_stored(self, db, registered_source, value, declared) -> None:
        outcome = ingest_raw(db, raw(value, declared=declared))
        db.commit()

        assert outcome.action == "rejected"
        assert outcome.reason, "a rejection must explain itself"
        # Never stored as an IOC.
        assert db.execute(select(func.count(Ioc.id))).scalar() == 0

    def test_rejection_is_audited_as_failure(self, db, registered_source) -> None:
        ingest_raw(db, raw("999.999.999.999", declared="IP"))
        db.commit()

        failed = db.execute(
            select(AuditLog).where(AuditLog.success.is_(False))
        ).scalars().all()
        assert failed, "rejections belong in the audit trail"
        assert failed[0].error


class TestDeduplication:
    def test_exact_duplicate_detected(self, db, registered_source) -> None:
        first = ingest_raw(db, raw("203.0.113.9", declared="IP"))
        second = ingest_raw(db, raw("203.0.113.9", declared="IP"))
        db.commit()

        assert first.action == "created"
        assert second.action == "updated"
        assert second.ioc_id == first.ioc_id
        assert db.execute(select(func.count(Ioc.id))).scalar() == 1

    def test_canonical_duplicate_detected(self, db, registered_source) -> None:
        """'Evil.Example.' and 'evil.example' are ONE indicator."""
        first = ingest_raw(db, raw("Evil.Example.", declared="DOMAIN"))
        second = ingest_raw(db, raw("evil.example", declared="DOMAIN"))
        db.commit()

        assert second.action == "updated"
        assert first.ioc_id == second.ioc_id
        assert db.execute(select(func.count(Ioc.id))).scalar() == 1

    def test_dedup_audited(self, db, registered_source) -> None:
        ingest_raw(db, raw("203.0.113.9", declared="IP"))
        ingest_raw(db, raw("203.0.113.9", declared="IP"))
        db.commit()

        dedup = db.execute(select(AuditLog).where(AuditLog.action == "DEDUP")).scalars().all()
        assert dedup, "duplicates must be traceable"

    def test_second_source_extends_provenance_not_count(self, db, registered_source) -> None:
        """Same provenance group -> one independent source (anti-collusion)."""
        ingest_raw(db, raw("203.0.113.9", declared="IP", source="test_source"))
        ingest_raw(db, raw("203.0.113.9", declared="IP", source="echo_of_test"))
        db.commit()

        links = db.execute(select(IocSource)).scalars().all()
        assert len(links) == 2                       # two feeds observed it
        groups = {l.source.provenance_group for l in links}
        assert len(groups) == 1                      # ...but ONE independent group

    def test_last_seen_refreshed_on_reobservation(self, db, registered_source) -> None:
        old = NOW - timedelta(days=5)
        first = ingest_raw(db, raw("203.0.113.9", declared="IP", first_seen=old))
        new = NOW - timedelta(hours=1)
        ingest_raw(db, raw("203.0.113.9", declared="IP", first_seen=new))
        db.commit()

        ioc = db.get(Ioc, first.ioc_id)
        assert ioc.last_seen_at >= new
        assert ioc.first_seen_at <= old


class TestSyntheticFlagging:
    def test_synthetic_flag_persisted(self, db, registered_source) -> None:
        outcome = ingest_raw(db, raw("192.0.2.10", declared="IP", synthetic=True))
        db.commit()

        ioc = db.get(Ioc, outcome.ioc_id)
        assert ioc.is_synthetic is True

    def test_real_data_not_marked_synthetic(self, db, registered_source) -> None:
        outcome = ingest_raw(db, raw("192.0.2.11", declared="IP"))
        db.commit()

        ioc = db.get(Ioc, outcome.ioc_id)
        assert ioc.is_synthetic is False


class TestExpiry:
    def test_expires_at_taken_from_source_not_invented(self, db, registered_source) -> None:
        expiry = NOW + timedelta(days=3)
        outcome = ingest_raw(db, raw(
            "192.0.2.20", declared="IP",
            ctx={"expires_at": expiry.isoformat()},
        ))
        db.commit()

        ioc = db.get(Ioc, outcome.ioc_id)
        assert ioc.expires_at is not None
        assert abs((ioc.expires_at - expiry).total_seconds()) < 1

    def test_no_expiry_date_means_none(self, db, registered_source) -> None:
        outcome = ingest_raw(db, raw("192.0.2.21", declared="IP"))
        db.commit()

        ioc = db.get(Ioc, outcome.ioc_id)
        assert ioc.expires_at is None   # never fabricated


class TestAuditImmutability:
    def test_database_rejects_update_and_delete(self, db, registered_source) -> None:
        ingest_raw(db, raw("203.0.113.9", declared="IP"))
        db.commit()

        # Each statement runs in its own transaction: a failed UPDATE aborts
        # the transaction, so the DELETE must not be attempted in it.
        with pytest.raises(Exception, match="append-only"):
            db.execute(text("UPDATE audit_logs SET actor = 'tampered'"))
        db.rollback()
        with pytest.raises(Exception, match="append-only"):
            db.execute(text("DELETE FROM audit_logs"))
        db.rollback()
