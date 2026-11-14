"""abuse.ch collectors — URLhaus, ThreatFox and MalwareBazaar.

The three endpoints require an abuse.ch Auth-Key (header ``Auth-Key``) created
at https://auth.abuse.ch/. Rules inherited from ``base.py``:

* no key -> ``CollectorError``: an unauthenticated call is never attempted and
  an empty feed is never reported as a success;
* a rejected key (``query_status`` other than ``ok``) -> ``CollectorError``
  carrying the server status, so the audit log shows the real reason;
* only fields returned by the API are used — nothing is inferred or invented.

Live status: these collectors were exercised against ``httpx.MockTransport``
only. No valid Auth-Key was available during the project, so the remote APIs
have never been called (documented in the report, chapter 18).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterator, Optional

import httpx

from app.collectors.base import BaseCollector, CollectorError, RawIndicator
from app.core.logging import get_logger

logger = get_logger("soar.collector.abusech")

URLHAUS_URL = "https://urlhaus-api.abuse.ch/v1/urls/recent/"
THREATFOX_URL = "https://threatfox-api.abuse.ch/api/v1/"
MALWAREBAZAAR_URL = "https://mb-api.abuse.ch/api/v1/"

# ThreatFox names its indicator types differently from our canonical types.
THREATFOX_TYPES: dict[str, str] = {
    "ip:port": "IP",
    "domain": "DOMAIN",
    "url": "URL",
    "md5_hash": "HASH_MD5",
    "sha1_hash": "HASH_SHA1",
    "sha256_hash": "HASH_SHA256",
}


class _AbuseChCollector(BaseCollector):
    """Shared Auth-Key handling and error mapping for the three abuse.ch feeds."""

    provenance_group = "abuse_ch"
    endpoint = ""

    def __init__(self, auth_key: str = "", timeout: float = 30.0, retries: int = 3,
                 transport: Any = None):
        self.auth_key = auth_key
        self.timeout = timeout
        self.retries = retries
        self.transport = transport  # httpx transport (tests inject a mock)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "User-Agent": "soar-ioc-factory/0.1"}
        if self.auth_key:
            headers["Auth-Key"] = self.auth_key
        return headers

    def _call(self, method: str = "POST", json_payload: Optional[dict] = None,
              data: Optional[dict] = None) -> dict[str, Any]:
        if not self.auth_key:
            raise CollectorError(
                f"{self.name}: abuse.ch Auth-Key missing (ABUSECH_AUTH_KEY). "
                "Create one at https://auth.abuse.ch/ — no unauthenticated call is attempted."
            )
        last_error: Exception | None = None
        payload: Any = None
        with httpx.Client(headers=self._headers(), timeout=self.timeout,
                          transport=self.transport) as client:
            for _attempt in range(self.retries):
                try:
                    # URLhaus answers only to GET ("http_get_expected"),
                    # ThreatFox and MalwareBazaar only to POST.
                    if method == "GET":
                        response = client.get(self.endpoint)
                    else:
                        response = client.post(self.endpoint, json=json_payload, data=data)
                    if response.status_code in (401, 403):
                        # No point retrying: the key itself is refused.
                        raise CollectorError(
                            f"{self.name}: abuse.ch refused the Auth-Key "
                            f"(HTTP {response.status_code})"
                        )
                    response.raise_for_status()
                    payload = response.json()
                    break
                except CollectorError:
                    raise
                except (httpx.HTTPError, ValueError) as exc:
                    last_error = exc
            else:
                raise CollectorError(
                    f"{self.name} request failed after {self.retries} attempts: {last_error}"
                )

        if not isinstance(payload, dict):
            raise CollectorError(f"{self.name}: payload is not a JSON object — refusing to guess")
        status = payload.get("query_status")
        if status not in (None, "ok"):
            raise CollectorError(
                f"{self.name}: abuse.ch rejected the call (query_status={status})"
            )
        return payload


class UrlhausCollector(_AbuseChCollector):
    """URLhaus recent URLs — one indicator per submitted malicious URL."""

    name = "urlhaus"
    endpoint = URLHAUS_URL

    def collect(self, limit: int = 100) -> Iterator[RawIndicator]:
        payload = self._call(method="GET")
        urls = payload.get("urls")
        if not isinstance(urls, list):
            raise CollectorError("urlhaus payload missing 'urls' — refusing to guess")

        count = 0
        for item in urls:
            if count >= limit:
                break
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            seen = _parse_time(item.get("date_added"))
            tags = [t for t in (item.get("tags") or []) if isinstance(t, str)][:10]
            yield RawIndicator(
                value=url,
                source_name=self.name,
                external_id=str(item["id"]) if item.get("id") is not None else None,
                external_url=item.get("urlhaus_reference"),
                first_seen_at=seen,
                last_seen_at=seen,
                tags=["urlhaus", *tags],
                context={
                    "feed": "urlhaus",
                    "declared_type": "URL",
                    "threat": item.get("threat"),
                    "url_status": item.get("url_status"),
                    "host": item.get("host"),
                },
            )
            count += 1

        if count == 0:
            raise CollectorError("urlhaus returned no indicators — refusing empty success")
        logger.info("urlhaus collect done", extra={"source": self.name, "action": "COLLECT"})


class ThreatFoxCollector(_AbuseChCollector):
    """ThreatFox IOCs of the last ``days`` days, mapped to canonical types."""

    name = "threatfox"
    endpoint = THREATFOX_URL

    def __init__(self, auth_key: str = "", days: int = 1, timeout: float = 30.0,
                 retries: int = 3, transport: Any = None):
        super().__init__(auth_key=auth_key, timeout=timeout, retries=retries,
                         transport=transport)
        self.days = days

    def collect(self, limit: int = 100) -> Iterator[RawIndicator]:
        try:
            payload = self._call(json_payload={"query": "get_iocs", "days": self.days})
        except CollectorError as exc:
            # "no_result" means "nothing in the window", not a broken call.
            if "query_status=no_result" in str(exc):
                logger.info("threatfox: no IOC in window",
                            extra={"source": self.name, "action": "COLLECT"})
                return
            raise

        data = payload.get("data")
        if not isinstance(data, list):
            raise CollectorError("threatfox payload missing 'data' — refusing to guess")

        count = 0
        for item in data:
            if count >= limit:
                break
            if not isinstance(item, dict):
                continue
            declared = THREATFOX_TYPES.get(str(item.get("ioc_type") or ""))
            raw_value = str(item.get("ioc") or "").strip()
            if declared is None or not raw_value:
                continue  # unsupported type (e.g. yara rule): skipped, never guessed
            value = raw_value
            if declared == "IP" and ":" in raw_value:
                # ThreatFox stores "1.2.3.4:8080"; the port is not part of the IOC
                value = raw_value.rsplit(":", 1)[0]
            first_seen = _parse_time(item.get("first_seen_utc"))
            last_seen = _parse_time(item.get("last_seen_utc")) or first_seen
            tags = [t for t in (item.get("tags") or []) if isinstance(t, str)][:10]
            malware = item.get("malware_printable") or item.get("malware")
            ioc_id = item.get("id")
            yield RawIndicator(
                value=value,
                source_name=self.name,
                external_id=str(ioc_id) if ioc_id is not None else None,
                external_url=f"https://threatfox.abuse.ch/ioc/{ioc_id}/" if ioc_id else None,
                first_seen_at=first_seen,
                last_seen_at=last_seen,
                tags=["threatfox", *tags],
                context={
                    "feed": "threatfox",
                    "declared_type": declared,
                    "threat_type": item.get("threat_type"),
                    "malware": malware,
                    "confidence_level": item.get("confidence_level"),
                },
            )
            count += 1

        if count == 0:
            raise CollectorError("threatfox returned no usable indicator — refusing empty success")
        logger.info("threatfox collect done", extra={"source": self.name, "action": "COLLECT"})


class MalwareBazaarCollector(_AbuseChCollector):
    """MalwareBazaar recent samples — one SHA-256 per sample (MD5/SHA-1 in context)."""

    name = "malwarebazaar"
    endpoint = MALWAREBAZAAR_URL

    def collect(self, limit: int = 100) -> Iterator[RawIndicator]:
        payload = self._call(data={"query": "get_recent", "selector": "time"})
        data = payload.get("data")
        if not isinstance(data, list):
            raise CollectorError("malwarebazaar payload missing 'data' — refusing to guess")

        count = 0
        for item in data:
            if count >= limit:
                break
            if not isinstance(item, dict):
                continue
            sha256 = str(item.get("sha256_hash") or "").strip().lower()
            if len(sha256) != 64:
                continue  # the normalizer would reject it anyway; never "repair" it
            seen = _parse_time(item.get("first_seen"))
            tags = [t for t in (item.get("tags") or []) if isinstance(t, str)][:10]
            signature = item.get("signature")
            yield RawIndicator(
                value=sha256,
                source_name=self.name,
                external_id=sha256,
                external_url=f"https://bazaar.abuse.ch/sample/{sha256}/",
                first_seen_at=seen,
                last_seen_at=seen,
                tags=["malwarebazaar", *([signature] if signature else []), *tags],
                context={
                    "feed": "malwarebazaar",
                    "declared_type": "HASH_SHA256",
                    "md5": item.get("md5_hash"),
                    "sha1": item.get("sha1_hash"),
                    "signature": signature,
                    "file_type": item.get("file_type"),
                },
            )
            count += 1

        if count == 0:
            raise CollectorError("malwarebazaar returned no indicator — refusing empty success")
        logger.info("malwarebazaar collect done",
                    extra={"source": self.name, "action": "COLLECT"})


def _parse_time(value: Any) -> Optional[datetime]:
    """Parse the two timestamp shapes abuse.ch uses, always returned in UTC."""
    if not value or not isinstance(value, str):
        return None
    text = value.strip().replace(" UTC", "+00:00")
    for fmt in ("%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None
