"""AbuseIPDB enrichment provider (API key required — verified live).

GET https://api.abuseipdb.com/api/v2/check
Header: Key: <ABUSEIPDB_API_KEY>

Verdict derived strictly from `abuseConfidenceScore`:
  >= 75 -> malicious,  >= 25 -> suspicious,  == 0 -> benign,  else unknown.
A provider failure returns an error — never a fabricated verdict.
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.logging import get_logger
from app.enrichment.service import ProviderResult
from app.models.ioc import Ioc, IocType

logger = get_logger("soar.enrichment.abuseipdb")

API = "https://api.abuseipdb.com/api/v2/check"


class AbuseIpdbProvider:
    """IP reputation from AbuseIPDB (Individual plan, 5 req/s)."""

    name = "abuseipdb"

    def __init__(self, api_key: str, timeout: float = 15.0, retries: int = 3,
                 transport: Any = None):
        if not api_key:
            raise ValueError("AbuseIPDB requires an API key")
        self.api_key = api_key
        self.timeout = timeout
        self.retries = retries
        self.transport = transport  # httpx transport (tests inject a mock)

    def supports(self, ioc: Ioc) -> bool:
        """AbuseIPDB covers IPv4/IPv6 only."""
        return ioc.type == IocType.IP

    def enrich(self, ioc: Ioc) -> ProviderResult:
        if not self.supports(ioc):  # defensive: skipped by run_enrichment
            return ProviderResult(provider=self.name, error="IP only")

        headers = {"Key": self.api_key, "Accept": "application/json",
                   "User-Agent": "soar-ioc-factory/0.1"}
        params = {"ipAddress": ioc.value, "maxAgeInDays": 30}

        last: Exception | None = None
        for attempt in range(self.retries):
            try:
                with httpx.Client(transport=self.transport, timeout=self.timeout) as client:
                    resp = client.get(API, params=params, headers=headers)
                if resp.status_code == 422:
                    # AbuseIPDB: IP is not public / invalid -> not an error of ours.
                    return ProviderResult(
                        provider=self.name, error=f"invalid/non-public IP: {resp.text[:120]}")
                resp.raise_for_status()
                data: dict[str, Any] = resp.json().get("data", {})
                break
            except httpx.HTTPError as exc:
                last = exc
                time.sleep(1 + attempt)
        else:
            return ProviderResult(provider=self.name,
                                  error=f"AbuseIPDB unreachable: {last}")

        score = data.get("abuseConfidenceScore")
        if score is None:
            return ProviderResult(provider=self.name,
                                  error="payload sans abuseConfidenceScore")

        score = int(score)
        if score >= 75:
            verdict = "malicious"
        elif score >= 25:
            verdict = "suspicious"
        elif score == 0:
            verdict = "benign"
        else:
            verdict = "unknown"

        # reputation in -100..100 : invert the confidence (0 abuse -> +100).
        reputation = max(-100, min(100, 100 - 2 * score))

        return ProviderResult(
            provider=self.name,
            verdict=verdict,
            reputation=reputation,
            data={
                "abuse_confidence_score": score,
                "total_reports": data.get("totalReports"),
                "num_distinct_users": data.get("numDistinctUsers"),
                "country_code": data.get("countryCode"),
                "isp": data.get("isp"),
                "usage_type": data.get("usageType"),
                "is_tor": data.get("isTor", False),
                "last_reported_at": data.get("lastReportedAt"),
            },
        )
