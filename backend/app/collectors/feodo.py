"""Feodo Tracker collector — botnet C2 IP blocklist, NO API KEY.

GET https://feodotracker.abuse.ch/downloads/ipblocklist.txt
Plain-text format: comment lines start with '#', one IP per line.
Sometimes shipped with ":port" suffixes — stripped by the normalizer.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

import httpx

from app.collectors.base import BaseCollector, CollectorError, RawIndicator
from app.core.logging import get_logger

logger = get_logger("soar.collector.feodo")

URL = "https://feodotracker.abuse.ch/downloads/ipblocklist.txt"


class FeodoCollector(BaseCollector):
    name = "feodotracker"
    provenance_group = "abuse_ch"   # SSLBL/URLhaus/ThreatFox share this group

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
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Feodo entries can be "IP:port"
            value = line.split(":", 1)[0] if line.count(":") == 1 else line
            count += 1
            yield RawIndicator(
                value=value,
                source_name=self.name,
                external_url=URL,
                first_seen_at=now,
                last_seen_at=now,
                tags=["botnet", "c2"],
                context={"feed": "feodo_tracker", "raw_line": line[:100]},
            )
        if count == 0:
            raise CollectorError("Feodo Tracker returned no indicators — refusing to guess")
        logger.info("feodo collect done", extra={"source": self.name, "action": "COLLECT"})

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
        raise CollectorError(f"Feodo Tracker unreachable after {self.retries} tries: {last_error}")
