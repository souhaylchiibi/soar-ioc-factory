"""Synthetic collector — clearly labelled fixtures for tests and demos.

Every indicator it yields carries `is_synthetic=True`, which is persisted
in `iocs.is_synthetic` so nothing synthetic can ever be mistaken for real
threat intelligence in the dashboard or in a report.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterator

from app.collectors.base import BaseCollector, RawIndicator

_NOW = datetime.now(timezone.utc)


def _entries() -> list[dict]:
    """A tiny, deterministic corpus covering every IOC type and edge case."""
    return [
        # --- valid, fresh, multi-source-worthy indicators -----------------
        {"value": "203.0.113.10", "type": "IP", "first_seen": _NOW - timedelta(hours=2),
         "tags": ["c2"], "external_id": "SYN-001"},
        {"value": "198.51.100.77", "type": "IP", "first_seen": _NOW - timedelta(days=1),
         "tags": ["scanner"], "external_id": "SYN-002"},
        {"value": "malware-lab.example", "type": "DOMAIN", "first_seen": _NOW - timedelta(hours=6),
         "tags": ["phishing"], "external_id": "SYN-003"},
        {"value": "http://malware-lab.example/payload.exe", "type": "URL",
         "first_seen": _NOW - timedelta(hours=6), "tags": ["dropper"], "external_id": "SYN-004"},
        {"value": "44d88612fea8a8f36de82e1278abb02f", "type": "HASH_MD5",   # eicar-like lab value
         "first_seen": _NOW - timedelta(days=3), "tags": ["test-file"], "external_id": "SYN-005"},
        {"value": "a94a8fe5ccb19ba61c4c0873d391e987982fbbd3", "type": "HASH_SHA1",
         "first_seen": _NOW - timedelta(days=10), "tags": ["test-file"], "external_id": "SYN-006"},
        {"value": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
         "type": "HASH_SHA256", "first_seen": _NOW - timedelta(days=40), "tags": ["old"],
         "external_id": "SYN-007"},
        # --- indicators designed to be duplicates ------------------------
        {"value": "203.0.113.10", "type": "IP", "first_seen": _NOW - timedelta(hours=1),
         "tags": ["c2"], "external_id": "SYN-001-DUP"},
        {"value": "MALWARE-LAB.EXAMPLE.", "type": "DOMAIN", "first_seen": _NOW - timedelta(hours=5),
         "tags": ["phishing"], "external_id": "SYN-003-DUP"},
        # --- invalid values: the pipeline must REJECT, never repair ------
        {"value": "999.999.999.999", "type": "IP", "external_id": "SYN-BAD-IP"},
        {"value": "not a domain!!", "type": "DOMAIN", "external_id": "SYN-BAD-DOMAIN"},
        {"value": "ftp://files.example/x", "type": "URL", "external_id": "SYN-BAD-SCHEME"},
        {"value": "zzzz8612fea8a8f36de82e1278abb02f", "type": "HASH_MD5", "external_id": "SYN-BAD-HASH"},
        # --- expired indicator -------------------------------------------
        {"value": "192.0.2.55", "type": "IP", "first_seen": _NOW - timedelta(days=30),
         "last_seen": _NOW - timedelta(days=30), "expires_at": _NOW - timedelta(days=1),
         "tags": ["expired-lab"], "external_id": "SYN-EXPIRED"},
    ]


class SyntheticCollector(BaseCollector):
    """Deterministic fixture source, marked as synthetic everywhere."""

    name = "synthetic_lab"
    provenance_group = "synthetic_lab"

    def __init__(self, only_valid: bool = False):
        self.only_valid = only_valid

    def collect(self, limit: int = 100) -> Iterator[RawIndicator]:
        for entry in _entries()[:limit]:
            last_seen = entry.get("last_seen") or entry.get("first_seen") or _NOW
            yield RawIndicator(
                value=entry["value"],
                source_name=self.name,
                external_id=entry.get("external_id"),
                external_url=None,
                first_seen_at=entry.get("first_seen"),
                last_seen_at=last_seen,
                tags=list(entry.get("tags") or []),
                context={
                    "declared_type": entry["type"],
                    "expires_at": entry.get("expires_at"),
                    "synthetic": True,
                },
                is_synthetic=True,
            )
