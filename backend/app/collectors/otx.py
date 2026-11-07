"""AlienVault OTX collector.

Two modes (both verified live against the API):
* WITH API key  -> GET /api/v1/pulses/subscribed  (auth required)
* WITHOUT key   -> GET /api/v1/pulses/latest      (may 404/403)

Failures raise CollectorError — an unreachable feed is recorded as an error,
never faked as an empty success.
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
# OTX returns several indicator shapes; only these are ingestible by us.
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

    def __init__(self, api_key: str = "", timeout: float = 20.0, page_sleep: float = 0.5,
                 transport: Any = None):
        self.api_key = api_key
        self.timeout = timeout
        self.page_sleep = page_sleep
        self.transport = transport  # httpx transport (tests inject a mock)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "User-Agent": "soar-ioc-factory/0.1"}
        if self.api_key:
            headers["X-OTX-API-KEY"] = self.api_key
        return headers

    def _fetch_page(self, client: httpx.Client, page: int) -> dict[str, Any]:
        if self.api_key:
            path, params = "/api/v1/pulses/subscribed", {"limit": 20, "page": page}
        else:
            path, params = "/api/v1/pulses/latest", {"limit": 20, "page": page}

        # Retries: this environment shows intermittent DNS failures
        # (Errno -5 / transient timeouts) — a single blip must not abort.
        last: Exception | None = None
        for attempt in range(3):
            try:
                resp = client.get(path, params=params)
                if resp.status_code in (401, 403):
                    raise CollectorError(
                        f"OTX {resp.status_code} (auth requise) - renseignez OTX_API_KEY"
                    )
                resp.raise_for_status()
                payload = resp.json()
                break
            except CollectorError:
                raise
            except httpx.HTTPError as exc:
                last = exc
                time.sleep(1.5 * (attempt + 1))
            except ValueError as exc:
                last = exc
                time.sleep(1.5 * (attempt + 1))
        else:
            raise CollectorError(f"OTX request failed after 3 attempts: {last}")

        if not isinstance(payload.get("results"), list):
            raise CollectorError("OTX payload missing 'results' - refusing to guess")
        return payload

    def collect(self, limit: int = 100) -> Iterator[RawIndicator]:
        """Stream indicators from subscribed/latest pulses (paginated)."""
        fetched = 0
        page = 1
        with httpx.Client(base_url=API_BASE, headers=self._headers(),
                          timeout=self.timeout, transport=self.transport) as client:
            while fetched < limit:
                payload = self._fetch_page(client, page)
                results = payload["results"]
                if not results:
                    break  # no more pages

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
                            # CVE/other types are skipped, never coerced.
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
                                "mode": "subscribed" if self.api_key else "latest",
                            },
                        )

                page += 1
                if self.page_sleep:
                    time.sleep(self.page_sleep)

        if fetched == 0:
            raise CollectorError("OTX returned 0 indicators - refusing empty success")
        logger.info("otx collect done",
                    extra={"source": self.name, "action": "COLLECT"})


def _parse_time(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None
