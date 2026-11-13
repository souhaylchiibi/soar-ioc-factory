"""Phase 7 - Security and integrity tests.

These tests check properties, not features:
* the audit trail is really append-only (SQL trigger),
* hostile input cannot become an indicator or reach SQL,
* the lifecycle refuses to skip steps,
* the anti-collusion rule counts independent organisations, not feeds,
* no secret is tracked by git and no port is published outside loopback,
* no credential pattern is hardcoded in the source tree.

Every assertion is made against the real PostgreSQL schema (see conftest.py)
or against the real repository files - nothing is mocked.
"""
from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.collectors.base import RawIndicator
from app.lifecycle.machine import LifecycleError, transition
from app.models.ioc import AuditLog, Ioc, IocSource, IocStatus, IocType, IntelSource
from app.services.ingest import ingest_raw
from app.services.normalization import NormalizationError, normalize

REPO = Path(__file__).resolve().parents[2]


def _raw(value: str, declared: str | None = None, source: str = "sec_source") -> RawIndicator:
    ctx = {"declared_type": declared} if declared else {}
    return RawIndicator(value=value, source_name=source, tags=[], context=ctx)


# --------------------------------------------------------------------------
# 1. Audit trail integrity
# --------------------------------------------------------------------------
class TestAuditImmutability:
    def test_audit_rows_cannot_be_updated(self, db) -> None:
        row = AuditLog(actor="test", action="SECURITY_CHECK", detail={"k": "v"})
        db.add(row)
        db.commit()
        row_id = row.id

        with pytest.raises(DBAPIError) as exc:
            db.execute(text("UPDATE audit_logs SET action='TAMPERED' WHERE id=:i"), {"i": row_id})
            db.commit()
        db.rollback()
        assert "append-only" in str(exc.value).lower()

        still = db.get(AuditLog, row_id)
        assert still is not None and still.action == "SECURITY_CHECK"

    def test_audit_rows_cannot_be_deleted(self, db) -> None:
        row = AuditLog(actor="test", action="SECURITY_CHECK", detail={"k": "v"})
        db.add(row)
        db.commit()
        row_id = row.id

        with pytest.raises(DBAPIError) as exc:
            db.execute(text("DELETE FROM audit_logs WHERE id=:i"), {"i": row_id})
            db.commit()
        db.rollback()
        assert "append-only" in str(exc.value).lower()

        assert db.execute(
            select(func.count(AuditLog.id)).where(AuditLog.id == row_id)
        ).scalar() == 1

    def test_trigger_is_present_in_schema(self, db) -> None:
        trig = db.execute(text(
            "SELECT tgname FROM pg_trigger WHERE tgname='trg_audit_immutable'"
        )).scalar()
        assert trig == "trg_audit_immutable"


# --------------------------------------------------------------------------
# 2. Hostile input
# --------------------------------------------------------------------------
HOSTILE_VALUES = [
    "'; DROP TABLE iocs; --",
    "1.1.1.1' OR '1'='1",
    '<script>alert(1)</script>',
    "../../../../etc/passwd",
    "0.0.0.0",
    "::1",
    "127.0.0.1",
    "169.254.169.254",   # link-local metadata endpoint
    "224.0.0.1",
    "not-an-indicator",
    "",
    "   ",
]


class TestHostileInput:
    @pytest.mark.parametrize("value", HOSTILE_VALUES)
    def test_normalization_rejects_hostile_values(self, value: str) -> None:
        with pytest.raises(NormalizationError):
            normalize(value)

    def test_injection_attempt_does_not_touch_the_table(self, db) -> None:
        before = db.execute(select(func.count(Ioc.id))).scalar()
        outcome = ingest_raw(db, _raw("'; DROP TABLE iocs; --", declared="IP"))
        db.commit()

        assert outcome.action == "rejected"
        # The table must still exist and be queryable.
        after = db.execute(select(func.count(Ioc.id))).scalar()
        assert after == before
        assert db.execute(text("SELECT to_regclass('public.iocs')")).scalar() == "iocs"

    def test_oversized_value_is_rejected_not_truncated(self) -> None:
        with pytest.raises(NormalizationError):
            normalize("a" * 5000 + ".com", IocType.DOMAIN)

    def test_explicit_type_mismatch_is_rejected(self) -> None:
        with pytest.raises(NormalizationError):
            normalize("203.0.113.7", IocType.DOMAIN)

    def test_shell_metacharacters_stay_inert_text(self) -> None:
        """A URL may contain `$()` - it must be stored as text, never executed."""
        url = "http://evil.example/$(id)"
        result = normalize(url, IocType.URL)
        assert result.value == url
        assert isinstance(result.value, str)


# --------------------------------------------------------------------------
# 3. Lifecycle cannot be short-circuited
# --------------------------------------------------------------------------
class TestLifecycleGuards:
    def test_new_cannot_jump_straight_to_published(self) -> None:
        ioc = Ioc(type=IocType.IP, value="203.0.113.10", raw_value="203.0.113.10",
                  status=IocStatus.NEW, fingerprint="a" * 64,
                  first_seen_at=datetime.now(timezone.utc),
                  last_seen_at=datetime.now(timezone.utc))
        with pytest.raises(LifecycleError):
            transition(ioc, IocStatus.PUBLISHED, reason="shortcut", actor="test")
        assert ioc.status == IocStatus.NEW

    def test_terminal_status_is_final(self) -> None:
        ioc = Ioc(type=IocType.IP, value="203.0.113.11", raw_value="203.0.113.11",
                  status=IocStatus.REMOVED, fingerprint="b" * 64,
                  first_seen_at=datetime.now(timezone.utc),
                  last_seen_at=datetime.now(timezone.utc))
        with pytest.raises(LifecycleError):
            transition(ioc, IocStatus.PUBLISHED, reason="resurrect", actor="test")


# --------------------------------------------------------------------------
# 4. Anti-collusion
# --------------------------------------------------------------------------
class TestAntiCollusion:
    def test_same_organisation_does_not_multiply_independent_sources(self, db) -> None:
        from app.services.pipeline import _independent_source_count

        group = IntelSource(name="feed_a", provenance_group="same_org", reliability=60)
        echo = IntelSource(name="feed_b", provenance_group="same_org", reliability=60)
        other = IntelSource(name="feed_c", provenance_group="other_org", reliability=80)
        db.add_all([group, echo, other])
        db.commit()

        outcome = ingest_raw(db, _raw("198.51.100.42", declared="IP"))
        db.commit()
        ioc = db.get(Ioc, outcome.ioc_id)
        assert ioc is not None

        db.add(IocSource(ioc_id=ioc.id, source_id=group.id))
        db.add(IocSource(ioc_id=ioc.id, source_id=echo.id))
        db.commit()
        assert _independent_source_count(db, ioc.id) == 1  # 2 feeds, 1 organisation

        db.add(IocSource(ioc_id=ioc.id, source_id=other.id))
        db.commit()
        assert _independent_source_count(db, ioc.id) == 2


# --------------------------------------------------------------------------
# 5. Repository hygiene: secrets and exposed ports
# --------------------------------------------------------------------------
def _tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True,
                         text=True, encoding="utf-8", errors="replace", timeout=60)
    assert out.returncode == 0, out.stderr
    return [line for line in out.stdout.splitlines() if line.strip()]


class TestRepositoryHygiene:
    def test_no_secret_file_is_tracked(self) -> None:
        tracked = _tracked_files()
        forbidden = [p for p in tracked
                     if p.endswith((".env", ".pem", ".key", ".p12", ".pfx"))
                     or Path(p).name == "credentials.json"]
        assert forbidden == [], f"secrets suivis par git: {forbidden}"

    def test_gitignore_covers_secrets(self) -> None:
        content = (REPO / ".gitignore").read_text(encoding="utf-8", errors="replace")
        for pattern in ("*.pem", "*.key", ".env", "credentials.json"):
            assert pattern in content, f"motif manquant dans .gitignore: {pattern}"

    def test_no_hardcoded_credential_pattern_in_source(self) -> None:
        patterns = {
            "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
            "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
            "slack_token": re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"),
        }
        scan_roots = ["backend/app", "scripts", "frontend/src", "infrastructure", "workflows"]
        offenders: list[str] = []
        for root in scan_roots:
            base = REPO / root
            if not base.exists():
                continue
            for path in base.rglob("*"):
                if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".ico", ".lock"}:
                    continue
                if path.stat().st_size > 400_000:
                    continue
                try:
                    content = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                for name, rx in patterns.items():
                    if rx.search(content):
                        offenders.append(f"{name}: {path.relative_to(REPO)}")
        assert offenders == [], f"motifs de credentials en dur: {offenders}"

    @pytest.mark.parametrize("compose_file", ["docker-compose.yml", "docker-compose.aws.yml"])
    def test_published_ports_are_loopback_only(self, compose_file: str) -> None:
        path = REPO / compose_file
        if not path.exists():
            pytest.skip(f"{compose_file} absent")
        content = path.read_text(encoding="utf-8", errors="replace")

        # Matches "127.0.0.1:8000:8000", "8000:8000", inline ["127.0.0.1:80:80"]
        # and long syntax is not used in this repository (checked below).
        mapping = re.compile(
            r"(?<![\w.:])(?:(\d{1,3}(?:\.\d{1,3}){3}):)?(\d{2,5}):(\d{2,5})(?:/(?:tcp|udp))?"
        )
        published = [(m.group(1), m.group(0)) for m in mapping.finditer(content)]

        assert published, f"aucune publication de port detectee dans {compose_file}"
        offenders = [text for host, text in published if host != "127.0.0.1"]
        assert offenders == [], f"ports non loopback dans {compose_file}: {offenders}"

        # Long syntax would bypass the check above: refuse it outright.
        assert "published:" not in content, (
            f"syntaxe longue de port detectee dans {compose_file} - verifier manuellement"
        )
