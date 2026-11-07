"""Phase 5/7 — OTX collector + AbuseIPDB provider (offline unit tests).

All tests use httpx.MockTransport: NO network access, deterministic results.
Live verification of both integrations was performed separately (real API).
"""
from __future__ import annotations

import json

import httpx
import pytest

from app.collectors.base import CollectorError
from app.collectors.otx import OtxCollector
from app.enrichment.abuseipdb import AbuseIpdbProvider
from app.enrichment.service import ProviderResult, run_enrichment
from app.models.ioc import Ioc, IocType


def make_ioc(value: str = "1.2.3.4", ioc_type: IocType = IocType.IP) -> Ioc:
    import uuid
    from datetime import datetime, timezone

    return Ioc(
        type=ioc_type, value=value, raw_value=value,
        fingerprint="f" * 64, id=uuid.uuid4(),
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
    )


# ------------------------------------------------------------------ OTX ----
def _otx_handler(request: httpx.Request) -> httpx.Response:
    """Scripted OTX API: asserts the key header and the endpoint used."""
    if "/pulses/subscribed" in str(request.url):
        if request.headers.get("X-OTX-API-KEY") != "k" * 64:
            return httpx.Response(403, json={"detail": "Authentication required"})
        return httpx.Response(200, json={
            "results": [
                {
                    "id": "p1", "name": "Lab pulse", "created": "2026-11-01T10:00:00Z",
                    "tags": ["lab"],
                    "indicators": [
                        {"type": "IPv4", "indicator": "203.0.113.7"},
                        {"type": "domain", "indicator": "evil.example"},
                        {"type": "CVE", "indicator": "CVE-2025-0001"},   # ignore
                        {"type": "FileHash-MD5", "indicator": "44d88612fea8a8f36de82e1278abb02f"},
                    ],
                },
                {"id": "p2", "name": "Empty pulse", "indicators": []},
            ]
        })
    if "/pulses/latest" in str(request.url):
        return httpx.Response(404, json={"detail": "endpoint not found"})
    return httpx.Response(404)


class TestOtxCollector:
    def test_with_key_uses_subscribed_and_harvests_supported_types(self) -> None:
        c = OtxCollector(api_key="k" * 64, page_sleep=0,
                         transport=httpx.MockTransport(_otx_handler))
        items = list(c.collect(limit=10))
        values = {i.value for i in items}
        # CVE must be skipped, others kept
        assert "203.0.113.7" in values
        assert "evil.example" in values
        assert "44d88612fea8a8f36de82e1278abb02f" in values
        assert not any("CVE-2025" in v for v in values)
        # declared_type carried for the normalizer
        by_value = {i.value: i for i in items}
        assert by_value["203.0.113.7"].context["declared_type"] == "IP"
        assert by_value["evil.example"].context["declared_type"] == "DOMAIN"
        assert by_value["203.0.113.7"].context["mode"] == "subscribed"

    def test_without_key_falls_back_to_latest(self) -> None:
        c = OtxCollector(api_key="", page_sleep=0,
                         transport=httpx.MockTransport(_otx_handler))
        # latest endpoint 404s in the mock: CollectorError, NOT an empty success
        with pytest.raises(CollectorError, match="OTX request failed after 3 attempts"):
            list(c.collect(limit=10))

    def test_forbidden_without_key_is_clear_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, json={"detail": "Authentication required"})

        c = OtxCollector(api_key="", page_sleep=0,
                         transport=httpx.MockTransport(handler))
        with pytest.raises(CollectorError, match="auth requise"):
            list(c.collect(limit=5))

    def test_empty_results_refuses_success(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"results": []})

        c = OtxCollector(api_key="k" * 64, page_sleep=0,
                         transport=httpx.MockTransport(handler))
        with pytest.raises(CollectorError, match="0 indicators"):
            list(c.collect(limit=5))

    def test_limit_is_respected(self) -> None:
        c = OtxCollector(api_key="k" * 64, page_sleep=0,
                         transport=httpx.MockTransport(_otx_handler))
        assert len(list(c.collect(limit=2))) == 2


# -------------------------------------------------------------- AbuseIPDB --
def _aipdb_handler_factory(score: int) -> httpx.Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Key") == "a" * 80, "cle absente du header"
        return httpx.Response(200, json={"data": {
            "ipAddress": "1.2.3.4", "abuseConfidenceScore": score,
            "totalReports": 12, "numDistinctUsers": 4,
            "countryCode": "FR", "isp": "Lab ISP", "usageType": "Data Center",
            "isTor": False, "lastReportedAt": "2026-11-01T00:00:00+00:00",
        }})
    return handler


class TestAbuseIpdbProvider:
    def test_requires_key(self) -> None:
        with pytest.raises(ValueError, match="API key"):
            AbuseIpdbProvider(api_key="")

    def test_supports_ip_only(self) -> None:
        p = AbuseIpdbProvider(api_key="a" * 80)
        assert p.supports(make_ioc("1.2.3.4", IocType.IP)) is True
        assert p.supports(make_ioc("evil.example", IocType.DOMAIN)) is False

    @pytest.mark.parametrize("score,verdict", [
        (0, "benign"), (10, "unknown"), (25, "suspicious"),
        (74, "suspicious"), (75, "malicious"), (100, "malicious"),
    ])
    def test_verdict_mapping(self, score: int, verdict: str) -> None:
        p = AbuseIpdbProvider(api_key="a" * 80,
                              transport=httpx.MockTransport(_aipdb_handler_factory(score)))
        out = p.enrich(make_ioc())
        assert out.ok
        assert out.verdict == verdict

    def test_reputation_is_inverted_and_bounded(self) -> None:
        p = AbuseIpdbProvider(api_key="a" * 80,
                              transport=httpx.MockTransport(_aipdb_handler_factory(90)))
        out = p.enrich(make_ioc())
        assert -100 <= out.reputation <= 100
        assert out.reputation < 0               # abusive IP => negative reputation
        assert out.data["abuse_confidence_score"] == 90

    def test_http_error_returns_error_not_verdict(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={})

        p = AbuseIpdbProvider(api_key="a" * 80, retries=1,
                              transport=httpx.MockTransport(handler))
        out = p.enrich(make_ioc())
        assert not out.ok
        assert out.verdict == "unknown"
        assert "unreachable" in out.error


# ------------------------------------------------- non-applicable skip ------
class TestEnrichmentSkip:
    def test_inapplicable_provider_is_skipped_not_counted_as_error(self, db) -> None:
        """AbuseIPDB on a DOMAIN must disappear from the batch, silently.

        Runs on the real PostgreSQL test schema (PG-only types: ARRAY/UUID/enums).
        """

        class DomainOnly:
            name = "domain_only"

            def supports(self, ioc: Ioc) -> bool:
                return ioc.type == IocType.DOMAIN

            def enrich(self, ioc: Ioc):
                raise AssertionError("must not be called for a non-domain")

        class AlwaysFails:
            name = "broken"

            def enrich(self, ioc: Ioc):
                return ProviderResult(provider=self.name, error="boom")

        ioc = make_ioc(f"1.2.{abs(hash('skip')) % 200}.4", IocType.IP)
        db.add(ioc)
        db.commit()

        summary = run_enrichment(db, ioc, [DomainOnly(), AlwaysFails()])
        # only the broken provider reported; the skip is silent
        assert [r.provider for r in summary.results] == ["broken"]
        assert len(summary.errors) == 1
        assert summary.verdicts == []
