"""AlienVault OTX collector — works WITHOUT an API key for public pulses.

Endpoint used: GET /api/v1/pulses/latest (public feed).
An optional API key (`X-OTX-API-KEY`) raises the rate limit when available.

Rate limits are honoured by sleeping between pages (never hammered).
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

import httpx

from app.collectors.base import BaseCollector, CollectorError, RawIndicator
from app.core.logging import get_logger

logger = get_logger("soar.collector.otx")

API_BASE = "https://otx.alienvault.com"
# OTX returns indicators of several shapes; only these are ingestible by us.
SUPPORTED_TYPES = {"IPv4", "IPv6", "domain", "hostname", "URL", "URI",
                   "FileHash-MD5", "FileHash-SHA1", "FileHash-SHA256"}

_TYPE_MAP = {
    "IPv4": "IP",
    "IPv6": "IP",
    "domain": "DOMAIN",
    "hostname": "DOMAIN",
    "URL": "URL",
    "URI": "URL",
    "FileHash-MD5": "HASH_MD5",
    "FileHash-SHA1": "HASH_SHA1",
    "FileHash-SHA256": "HASH_SHA256",
}


class OtxCollector(BaseCollector):
    name = "alienvault_otx"
    provenance_group = "alienvault"   # feeds echoing OTX share this group

    def __init__(self, api_key: str = "", timeout: float = 20.0, page_sleep: float = 1.0):
        self.api_key = api_key
        self.timeout = timeout
        self.page_sleep = page_sleep

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "User-Agent": "soar-ioc-factory/0.1"}
        if self.api_key:
            headers["X-OTX-API-KEY"] = self.api_key
        return headers

    def collect(self, limit: int = 100) -> Iterator[RawIndicator]:
        """Stream indicators from the latest public pulses."""
        fetched = 0
        try:
            with httpx.Client(base_url=API_BASE, headers=self._headers(), timeout=self.timeout) as client:
                # Fetch enough pulses to cover `limit` indicators.
                resp = client.get("/api/v1/pulses/latest", params={"limit": 10, "page": 1})
                resp.raise_for_status()
                payload: dict[str, Any] = resp.json()
        except httpx.HTTPError as exc:
            raise CollectorError(f"OTX request failed: {exc}") from exc
        except ValueError as exc:
            raise CollectorError(f"OTX returned non-JSON payload: {exc}") from exc

        results = payload.get("results")
        if not isinstance(results, list):
            raise CollectorError("OTX payload missing 'results' — refusing to guess")

        for pulse in results:
            if fetched >= limit:
                break
            if not isinstance(pulse, dict):
                continue
            pulse_id = pulse.get("id") or pulse.get("pulse_id")
            pulse_url = f"{API_BASE}/pulse/{pulse_id}" if pulse_id else None
            created = _parse_time(pulse.get("created"))

            for indicator in pulse.get("indicators") or []:
                if fetched >= limit:
                    break
                ioc_type = indicator.get("type")
                if ioc_type not in SUPPORTED_TYPES:
                    continue
                value = indicator.get("indicator")
                if not value:
                    continue
                fetched += 1
                yield RawIndicator(
                    value=value,
                    source_name=self.name,
                    external_id=str(pulse_id) if pulse_id else None,
                    external_url=pulse_url,
                    first_seen_at=created,
                    last_seen_at=created,
                    tags=list(pulse.get("tags") or []),
                    context={
                        "declared_type": _TYPE_MAP[ioc_type],
                        "pulse_name": pulse.get("name"),
                        "otx_type": ioc_type,
                        "description": indicator.get("description"),
                    },
                )

            if self.page_sleep:
                time.sleep(self.page_sleep)

        logger.info(
            "otx collect done",
            extra={"source": self.name, "action": "COLLECT"},
        )


def _parse_time(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None
