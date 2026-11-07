"""blocklist.de collector — community attack-source IPs, NO API KEY.

GET https://lists.blocklist.de/lists/all.txt
One IPv4 per line, no comments. Mixed attack types (ssh, mail, apache…).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

import httpx

from app.collectors.base import BaseCollector, CollectorError, RawIndicator
from app.core.logging import get_logger

logger = get_logger("soar.collector.blocklist_de")

URL = "https://lists.blocklist.de/lists/all.txt"


class BlocklistDeCollector(BaseCollector):
    name = "blocklist_de"
    provenance_group = "blocklist_de"

    def __init__(self, timeout: float = 30.0, retries: int = 3):
        self.timeout = timeout
        self.retries = retries

    def collect(self, limit: int = 100) -> Iterator[RawIndicator]:
        text = self._fetch()
        now = datetime.now(timezone.utc)
        count = 0
        for line in text.splitlines():
            if count >= limit:
                break
            value = line.strip()
            if not value or value.startswith("#"):
                continue
            count += 1
            yield RawIndicator(
                value=value,
                source_name=self.name,
                external_url=URL,
                first_seen_at=now,
                last_seen_at=now,
                tags=["scanner", "community-blocklist"],
                context={"feed": "blocklist_de"},
            )
        if count == 0:
            raise CollectorError("blocklist.de returned no indicators — refusing to guess")
        logger.info("blocklist_de collect done", extra={"source": self.name, "action": "COLLECT"})

    def _fetch(self) -> str:
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                resp = httpx.get(URL, timeout=self.timeout,
                                 headers={"User-Agent": "soar-ioc-factory/0.1"})
                resp.raise_for_status()
                return resp.text
            except httpx.HTTPError as exc:
                last_error = exc
        raise CollectorError(f"blocklist.de unreachable after {self.retries} tries: {last_error}")
