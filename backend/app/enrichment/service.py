"""Enrichment aggregation.

Collects verdicts from several providers, stores each result, and produces
the aggregated view consumed by the scoring engine.

Rules:
* providers never fabricate data — a provider that fails is skipped and
  recorded as an error, NOT returned as "benign",
* results are cached per (ioc, provider) with an expiry,
* verdicts are normalized to: malicious | suspicious | benign | unknown.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.ioc import Enrichment, Ioc

logger = get_logger("soar.enrichment")

VERDICTS = ("malicious", "suspicious", "benign", "unknown")

# Provider API contract.
class EnrichmentProvider(Protocol):
    name: str

    def enrich(self, ioc: Ioc) -> "ProviderResult": ...


@dataclass
class ProviderResult:
    provider: str
    verdict: str = "unknown"          # malicious | suspicious | benign | unknown
    reputation: Optional[int] = None  # -100..100
    data: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None       # provider failed -> data is NOT invented

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class EnrichmentSummary:
    ioc_id: str
    results: list[ProviderResult] = field(default_factory=list)

    @property
    def verdicts(self) -> list[str]:
        """Verdicts of providers that actually answered."""
        return [r.verdict for r in self.results if r.ok]

    @property
    def errors(self) -> list[ProviderResult]:
        return [r for r in self.results if not r.ok]

    @property
    def best_reputation(self) -> Optional[int]:
        reps = [r.reputation for r in self.results if r.ok and r.reputation is not None]
        return min(reps) if reps else None  # most conservative


def normalize_verdict(value: Any) -> str:
    """Map provider-specific wording onto our four verdicts."""
    if not isinstance(value, str):
        return "unknown"
    v = value.strip().lower()
    if v in ("malicious", "malware", "malicious score", "phishing", "c2", "bad"):
        return "malicious"
    if v in ("suspicious", "suspicious score", "suspected", "graylist"):
        return "suspicious"
    if v in ("benign", "clean", "whitelist", "good", "not listed"):
        return "benign"
    return "unknown"


def run_enrichment(
    db: Session,
    ioc: Ioc,
    providers: list[Any],
    ttl_hours: int = 24,
    force: bool = False,
) -> EnrichmentSummary:
    """Run every provider against `ioc`, persist results, return the summary.

    Failures are captured per provider and never abort the whole run.
    """
    summary = EnrichmentSummary(ioc_id=str(ioc.id))
    now = datetime.now(timezone.utc)

    for provider in providers:
        # Cache hit?
        if not force:
            cached = db.execute(
                select(Enrichment).where(
                    Enrichment.ioc_id == ioc.id,
                    Enrichment.provider == provider.name,
                    Enrichment.fetched_at >= now - timedelta(hours=ttl_hours),
                )
            ).scalars().first()
            if cached is not None:
                summary.results.append(ProviderResult(
                    provider=provider.name,
                    verdict=cached.verdict or "unknown",
                    reputation=cached.reputation,
                    data={"cached": True},
                ))
                continue

        try:
            result = provider.enrich(ioc)
        except Exception as exc:  # provider bug/network must not kill the run
            logger.warning(
                "enrichment provider failed",
                extra={"source": provider.name, "action": "ENRICH"},
            )
            result = ProviderResult(provider=provider.name, error=f"{type(exc).__name__}: {exc}")

        result.verdict = normalize_verdict(result.verdict) if result.ok else "unknown"

        db.add(Enrichment(
            ioc_id=ioc.id,
            provider=result.provider,
            data=result.data if result.ok else {"error": result.error},
            verdict=result.verdict,
            reputation=result.reputation,
            is_synthetic=ioc.is_synthetic,
            expires_at=now + timedelta(hours=ttl_hours),
        ))
        summary.results.append(result)

    db.flush()
    return summary
