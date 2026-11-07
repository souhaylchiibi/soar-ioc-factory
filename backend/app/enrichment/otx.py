"""OTX enrichment provider — uses the PUBLIC indicator endpoint (no API key).

GET /api/v1/indicators/{type}/{value}/general
The verdict is derived ONLY from fields present in the response
(pulse count, reputation, listed flags). When the provider cannot answer,
an error is returned — a verdict is never guessed.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.core.logging import get_logger
from app.enrichment.service import ProviderResult
from app.models.ioc import Ioc, IocType

logger = get_logger("soar.enrichment.otx")

API_BASE = "https://otx.alienvault.com"

# Our type -> OTX indicator path segment.
_OTX_TYPE = {
    IocType.IP: "IPv4",
    IocType.DOMAIN: "domain",
    IocType.URL: "URL",
    IocType.HASH_MD5: "FileHash-MD5",
    IocType.HASH_SHA1: "FileHash-SHA1",
    IocType.HASH_SHA256: "FileHash-SHA256",
}


class OtxEnrichmentProvider:
    """Read-only OTX lookup. Works without an API key (rate limits apply)."""

    name = "otx"

    def __init__(self, api_key: str = "", timeout: float = 15.0):
        self.api_key = api_key
        self.timeout = timeout

    def enrich(self, ioc: Ioc) -> ProviderResult:
        otx_type = _OTX_TYPE.get(ioc.type)
        if otx_type is None:
            return ProviderResult(provider=self.name, error=f"unsupported type {ioc.type.value}")

        headers = {"Accept": "application/json", "User-Agent": "soar-ioc-factory/0.1"}
        if self.api_key:
            headers["X-OTX-API-KEY"] = self.api_key

        url = f"{API_BASE}/api/v1/indicators/{otx_type}/{ioc.value}/general"
        try:
            with httpx.Client(headers=headers, timeout=self.timeout, follow_redirects=True) as client:
                resp = client.get(url)
                if resp.status_code == 404:
                    # Not known to OTX: that is information, not an error.
                    return ProviderResult(
                        provider=self.name, verdict="unknown",
                        data={"known_to_otx": False},
                    )
                resp.raise_for_status()
                payload: dict[str, Any] = resp.json()
        except httpx.HTTPError as exc:
            # Network/rate-limit failure: NO verdict is invented.
            return ProviderResult(provider=self.name, error=f"OTX unreachable: {exc}")
        except ValueError as exc:
            return ProviderResult(provider=self.name, error=f"OTX non-JSON: {exc}")

        pulse_info = payload.get("pulse_info") or {}
        pulse_count = int(pulse_info.get("count") or 0)
        reputation = payload.get("reputation")
        # Verdict derived strictly from observed data.
        if pulse_count >= 5:
            verdict = "malicious"
        elif pulse_count >= 1:
            verdict = "suspicious"
        else:
            verdict = "unknown"

        rep = int(reputation) if isinstance(reputation, (int, float)) else None
        if rep is not None:
            rep = max(-100, min(100, rep))

        return ProviderResult(
            provider=self.name,
            verdict=verdict,
            reputation=rep,
            data={
                "known_to_otx": True,
                "pulse_count": pulse_count,
                "reputation": rep,
                "pulse_names": [p.get("name") for p in (pulse_info.get("pulses") or [])[:5]],
            },
        )
