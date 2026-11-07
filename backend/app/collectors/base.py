"""Collector contract shared by every source integration.

Rules enforced by this module:
* a collector NEVER invents indicators: it yields what the source returned,
* failures raise `CollectorError` — the caller records them (no silent empties),
* rate limiting / backoff are the caller's job (see services/ingest.py),
* every yield carries provenance (source name + external id/url).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator, Optional


class CollectorError(RuntimeError):
    """Source unreachable, misconfigured or returned an unusable payload."""


@dataclass
class RawIndicator:
    """As-received indicator, before normalization."""

    value: str
    source_name: str
    external_id: Optional[str] = None
    external_url: Optional[str] = None
    # Observed timestamps from the source (fallback: now).
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    tags: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    # Set by the collector when the data is a fixture for tests/demos.
    is_synthetic: bool = False


class BaseCollector(ABC):
    """Base class: identifies the source and exposes `collect()`."""

    name: str = "base"
    provenance_group: str = "base"

    @abstractmethod
    def collect(self, limit: int = 100) -> Iterator[RawIndicator]:
        """Yield indicators. Must raise CollectorError on failure."""

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{type(self).__name__} source={self.name!r}>"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
