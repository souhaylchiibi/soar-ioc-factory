"""urlscan.io collector — public scan results (domains + URLs), NO API KEY.

GET https://urlscan.io/api/v1/search/?q=...&size=...

IMPORTANT: queries MUST be non-empty and valid — an empty result set means
"nothing matched", not "feed is empty", and no indicator is invented.
Only `task.domain` (and page.url when host is a domain) is harvested; we do
not submit or store full page content.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

import httpx

from app.collectors.base import BaseCollector, CollectorError, RawIndicator
from app.core.logging import get_logger

logger = get_logger("soar.collector.urlscan")

SEARCH_URL = "https://urlscan.io/api/v1/search/"


class UrlscanCollector(BaseCollector):
    name = "urlscan"
    provenance_group = "urlscan"

    def __init__(self, query: str = "task.domain:*", timeout: float = 30.0, retries: int = 3):
        self.query = query
        self.timeout = timeout
        self.retries = retries

    def collect(self, limit: int = 100) -> Iterator[RawIndicator]:
        payload = self._search()
        results = payload.get("results")
        if not isinstance(results, list):
            raise CollectorError("urlscan payload missing 'results' — refusing to guess")

        count = 0
        for item in results:
            if count >= limit:
                break
            if not isinstance(item, dict):
                continue
            task = item.get("task") or {}
            page = item.get("page") or {}
            # Prefer the domain field; fall back to page domain.
            domain = task.get("domain") or page.get("domain")
            if not domain:
                continue
            seen = _parse_time(task.get("time"))
            yield RawIndicator(
                value=domain,
                source_name=self.name,
                external_id=task.get("uuid"),
                external_url=f"https://urlscan.io/result/{task.get('uuid')}" if task.get("uuid") else None,
                first_seen_at=seen,
                last_seen_at=seen,
                tags=["urlscan", "scan"],
                context={"feed": "urlscan_search", "query": self.query,
                         "declared_type": "DOMAIN",   # task.domain is a hostname
                         "page_url": (page.get("url") or "")[:300]},
            )
            count += 1

        if count == 0:
            # Not an error: the query simply matched nothing right now.
            logger.info("urlscan returned 0 matches", extra={"source": self.name, "action": "COLLECT"})
        else:
            logger.info("urlscan collect done",
                        extra={"source": self.name, "action": "COLLECT"})

    def _search(self) -> dict:
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                resp = httpx.get(
                    SEARCH_URL, params={"q": self.query, "size": 100},
                    timeout=self.timeout, headers={"User-Agent": "soar-ioc-factory/0.1",
                                                   "Accept": "application/json"},
                )
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
        raise CollectorError(f"urlscan unreachable after {self.retries} tries: {last_error}")


def _parse_time(value):
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None
