"""abuse.ch collectors — offline unit tests (URLhaus, ThreatFox, MalwareBazaar).

Every call goes through ``httpx.MockTransport``: no network, no key required.
The live APIs have never been called: the Auth-Key provided during the project
was rejected by abuse.ch (``unknown_auth_key``), and that fact is reported as
such instead of being simulated.
"""
from __future__ import annotations

from datetime import timezone

import httpx
import pytest

from app.collectors.abusech import (
    MalwareBazaarCollector,
    ThreatFoxCollector,
    UrlhausCollector,
)
from app.collectors.base import CollectorError

KEY = "k" * 64


# ----------------------------------------------------------------- URLhaus --
def _urlhaus_handler(calls: list[httpx.Request]):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.method != "GET":
            # Real API answer: POST is refused with http_get_expected
            return httpx.Response(405, json={"query_status": "http_get_expected"})
        if request.headers.get("Auth-Key") != KEY:
            return httpx.Response(401, json={"query_status": "unknown_auth_key"})
        return httpx.Response(200, json={
            "query_status": "ok",
            "urls": [
                {
                    "id": "3100001",
                    "urlhaus_reference": "https://urlhaus.abuse.ch/url/3100001/",
                    "url": "http://malware-lab.example/payload.elf",
                    "url_status": "online",
                    "host": "malware-lab.example",
                    "date_added": "2026-11-14 01:02:03 UTC",
                    "threat": "malware_download",
                    "tags": ["elf", "mozi"],
                },
                {
                    "id": "3100002",
                    "url": "http://203.0.113.10/gate.php",
                    "host": "203.0.113.10",
                    "date_added": "2026-11-14 00:30:00 UTC",
                    "threat": "malware_download",
                    "tags": ["php"],
                },
            ],
        })
    return handler


class TestUrlhaus:
    def test_requires_auth_key_before_any_call(self) -> None:
        calls: list[httpx.Request] = []
        collector = UrlhausCollector(auth_key="", transport=httpx.MockTransport(
            _urlhaus_handler(calls)))
        with pytest.raises(CollectorError, match="ABUSECH_AUTH_KEY"):
            list(collector.collect())
        assert calls == [], "aucun appel ne doit partir sans cle"

    def test_maps_urls_with_provenance(self) -> None:
        calls: list[httpx.Request] = []
        collector = UrlhausCollector(auth_key=KEY, transport=httpx.MockTransport(
            _urlhaus_handler(calls)))
        items = list(collector.collect(limit=10))

        assert len(items) == 2
        assert calls[0].method == "GET", "URLhaus n'accepte que GET (http_get_expected)"
        assert calls[0].headers["Auth-Key"] == KEY
        first = items[0]
        assert first.value == "http://malware-lab.example/payload.elf"
        assert first.context["declared_type"] == "URL"
        assert first.external_id == "3100001"
        assert "urlhaus" in first.tags
        assert first.first_seen_at is not None
        assert first.first_seen_at.tzinfo is not None
        assert first.first_seen_at.astimezone(timezone.utc).hour == 1

    def test_respects_limit(self) -> None:
        collector = UrlhausCollector(auth_key=KEY, transport=httpx.MockTransport(
            _urlhaus_handler([])))
        assert len(list(collector.collect(limit=1))) == 1

    def test_rejected_key_is_an_error_not_an_empty_success(self) -> None:
        # Real behaviour of the API as observed during the project: HTTP 200
        # with a query_status body, not a 401.
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"query_status": "unknown_auth_key"})

        collector = UrlhausCollector(auth_key="wrong",
                                     transport=httpx.MockTransport(handler))
        with pytest.raises(CollectorError, match="unknown_auth_key"):
            list(collector.collect())

    def test_http_401_stops_immediately_without_retrying(self) -> None:
        attempts: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            attempts.append(1)
            return httpx.Response(401, json={"query_status": "unknown_auth_key"})

        collector = UrlhausCollector(auth_key="wrong", retries=3,
                                     transport=httpx.MockTransport(handler))
        with pytest.raises(CollectorError, match="refused the Auth-Key"):
            list(collector.collect())
        assert len(attempts) == 1, "une cle refusee ne doit pas etre rejouee"

    def test_retries_then_fails_on_server_error(self) -> None:
        attempts: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            attempts.append(1)
            return httpx.Response(503, text="unavailable")

        collector = UrlhausCollector(auth_key=KEY, retries=3,
                                     transport=httpx.MockTransport(handler))
        with pytest.raises(CollectorError, match="failed after 3 attempts"):
            list(collector.collect())
        assert len(attempts) == 3


# --------------------------------------------------------------- ThreatFox --
def _threatfox_payload() -> dict:
    return {
        "query_status": "ok",
        "data": [
            {
                "id": "1500001",
                "ioc": "198.51.100.7:8443",
                "ioc_type": "ip:port",
                "threat_type": "botnet_cc",
                "malware_printable": "Cobalt Strike",
                "confidence_level": 75,
                "first_seen_utc": "2026-11-13 10:00:00",
                "last_seen_utc": "2026-11-14 00:00:00",
                "tags": ["c2"],
            },
            {
                "id": "1500002",
                "ioc": "update.malware-lab.example",
                "ioc_type": "domain",
                "threat_type": "payload_delivery",
                "confidence_level": 50,
                "first_seen_utc": "2026-11-12 08:00:00",
            },
            {
                "id": "1500003",
                "ioc": "rule Example { condition: true }",
                "ioc_type": "yara",
                "threat_type": "malware",
            },
            {
                "id": "1500004",
                "ioc": "d41d8cd98f00b204e9800998ecf8427e",
                "ioc_type": "md5_hash",
                "confidence_level": 100,
            },
        ],
    }


class TestThreatFox:
    def _collector(self, payload: dict) -> ThreatFoxCollector:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers.get("Auth-Key") == KEY
            return httpx.Response(200, json=payload)

        return ThreatFoxCollector(auth_key=KEY, transport=httpx.MockTransport(handler))

    def test_strips_port_maps_types_and_skips_unsupported(self) -> None:
        items = list(self._collector(_threatfox_payload()).collect(limit=10))
        values = {i.value: i for i in items}

        assert "198.51.100.7" in values, "le port ne fait pas partie de l'IOC"
        assert values["198.51.100.7"].context["declared_type"] == "IP"
        assert values["update.malware-lab.example"].context["declared_type"] == "DOMAIN"
        assert values["d41d8cd98f00b204e9800998ecf8427e"].context["declared_type"] == "HASH_MD5"
        assert not any("yara" in (i.context or {}).get("declared_type", "") for i in items)
        assert len(items) == 3, "la regle YARA doit etre ignoree, pas devinee"

    def test_empty_window_is_not_an_error(self) -> None:
        collector = self._collector({"query_status": "no_result", "data": []})
        assert list(collector.collect()) == []

    def test_missing_data_is_an_error(self) -> None:
        collector = self._collector({"query_status": "ok"})
        with pytest.raises(CollectorError, match="missing 'data'"):
            list(collector.collect())


# ----------------------------------------------------------- MalwareBazaar --
SHA256 = "a" * 64


def _bazaar_payload() -> dict:
    return {
        "query_status": "ok",
        "data": [
            {
                "sha256_hash": SHA256.upper(),
                "sha1_hash": "b" * 40,
                "md5_hash": "c" * 32,
                "first_seen": "2026-11-14 00:10:00",
                "file_type": "exe",
                "signature": "AgentTesla",
                "tags": ["exe", "stealer"],
            },
            {"sha256_hash": "not-a-hash", "first_seen": "2026-11-14 00:11:00"},
        ],
    }


class TestMalwareBazaar:
    def _collector(self, payload: dict) -> MalwareBazaarCollector:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers.get("Auth-Key") == KEY
            assert b"get_recent" in request.content
            return httpx.Response(200, json=payload)

        return MalwareBazaarCollector(auth_key=KEY, transport=httpx.MockTransport(handler))

    def test_keeps_sha256_and_rejects_malformed_hash(self) -> None:
        items = list(self._collector(_bazaar_payload()).collect(limit=10))
        assert len(items) == 1, "une empreinte invalide est ignoree, jamais reparee"
        sample = items[0]
        assert sample.value == SHA256
        assert sample.context["declared_type"] == "HASH_SHA256"
        assert sample.context["md5"] == "c" * 32
        assert "AgentTesla" in sample.tags
        assert sample.external_url.rstrip("/").endswith(SHA256)

    def test_empty_answer_is_an_error(self) -> None:
        collector = self._collector({"query_status": "ok", "data": []})
        with pytest.raises(CollectorError, match="no indicator"):
            list(collector.collect())


# --------------------------------------------------------------- communs ----
@pytest.mark.parametrize("cls", [UrlhausCollector, ThreatFoxCollector,
                                 MalwareBazaarCollector])
def test_every_collector_declares_the_abuse_ch_group(cls) -> None:
    assert cls.provenance_group == "abuse_ch"
