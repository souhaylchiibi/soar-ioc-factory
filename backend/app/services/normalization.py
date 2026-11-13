"""Normalization + validation of raw indicators.

Guarantees:
* one canonical form per indicator (the dedup fingerprint depends on it),
* strict validation (invalid input is rejected, never stored as-is),
* NO invented data: a value that fails validation raises, it is not "fixed".
"""
from __future__ import annotations

import hashlib
import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from app.models.ioc import IocType

# RFC 1035 label rules, with a practical TLD requirement (>=2 chars, letters).
_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z]{2,63}$"
)

# MD5 / SHA1 / SHA256
_HASH_RE = {
    IocType.HASH_MD5: re.compile(r"^[a-f0-9]{32}$"),
    IocType.HASH_SHA1: re.compile(r"^[a-f0-9]{40}$"),
    IocType.HASH_SHA256: re.compile(r"^[a-f0-9]{64}$"),
}

_HASH_TYPES_BY_LENGTH = {32: IocType.HASH_MD5, 40: IocType.HASH_SHA1, 64: IocType.HASH_SHA256}


class NormalizationError(ValueError):
    """Raised when a raw value cannot be validated. Never swallow it silently."""


@dataclass(frozen=True)
class NormalizedIoc:
    type: IocType
    value: str  # canonical form
    raw_value: str
    fingerprint: str  # sha256 of "TYPE:value"


def compute_fingerprint(ioc_type: IocType, value: str) -> str:
    return hashlib.sha256(f"{ioc_type.value}:{value}".encode()).hexdigest()


# ------------------------------------------------------------------ IP ----
def normalize_ip(raw: str) -> str:
    candidate = raw.strip()
    # Accept "IP:port" (common in Suricata logs) but canonicalize the IP alone.
    if candidate.count(":") == 1 and not candidate.startswith("["):
        candidate = candidate.split(":", 1)[0]
    try:
        addr = ipaddress.ip_address(candidate)
    except ValueError as exc:
        raise NormalizationError(f"invalid IP address: {raw!r}") from exc
    # Non-routable noise (0.0.0.0, ::1, link-local, multicast) is not a threat
    # indicator worth storing. NOTE: private ranges are kept on purpose --
    # internal incident response feeds legitimately reference RFC1918 hosts.
    if addr.is_unspecified or addr.is_multicast or addr.is_loopback or addr.is_link_local:
        raise NormalizationError(f"non-routable or multicast IP rejected: {raw!r}")
    return str(addr)


# -------------------------------------------------------------- DOMAIN ----
def normalize_domain(raw: str) -> str:
    candidate = raw.strip().lower().rstrip(".")
    # A URL in a DOMAIN field is a source error: reject, never "repair" it
    # silently (the canonical value must be trustworthy).
    if "://" in candidate:
        raise NormalizationError(f"URL supplied where a domain was expected: {raw!r}")
    # Strip port and trailing dot.
    if ":" in candidate:
        candidate = candidate.split(":", 1)[0]
    if not _DOMAIN_RE.match(candidate):
        raise NormalizationError(f"invalid domain: {raw!r}")
    return candidate


# ----------------------------------------------------------------- URL ----
def normalize_url(raw: str) -> str:
    candidate = raw.strip()
    parts = urlsplit(candidate)
    if parts.scheme not in ("http", "https"):
        raise NormalizationError(f"unsupported URL scheme: {raw!r}")
    if not parts.hostname:
        raise NormalizationError(f"URL without host: {raw!r}")
    # Validate the host too (an IP host is fine).
    host = parts.hostname.lower()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not _DOMAIN_RE.match(host):
            raise NormalizationError(f"URL with invalid host: {raw!r}")
    # Canonical form: lowercase scheme/host, drop fragment, keep path/query.
    # Default ports are removed so http://x:80/ == http://x/.
    port = parts.port
    if port and not (
        (parts.scheme == "http" and port == 80) or (parts.scheme == "https" and port == 443)
    ):
        netloc = f"{host}:{port}"
    else:
        netloc = host
    if parts.username:
        netloc = f"{parts.username}:{parts.password or ''}@{netloc}"
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "", parts.query, ""))


# ---------------------------------------------------------------- hash ----
def normalize_hash(raw: str) -> tuple[IocType, str]:
    candidate = raw.strip().lower()
    ioc_type = _HASH_TYPES_BY_LENGTH.get(len(candidate))
    if ioc_type is None:
        raise NormalizationError(f"hash with unexpected length {len(raw.strip())}: {raw!r}")
    if not _HASH_RE[ioc_type].match(candidate):
        raise NormalizationError(f"invalid hex digest: {raw!r}")
    return ioc_type, candidate


# ------------------------------------------------------------- facade ------
def normalize(raw: str, declared_type: IocType | None = None) -> NormalizedIoc:
    """Validate and canonicalize one indicator.

    If `declared_type` is given, the value must match it. Otherwise the type
    is inferred — but only for unambiguous shapes (hashes, IP, URL); domains
    require an explicit type to avoid ambiguity with a bare hostname.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise NormalizationError("empty indicator")

    if declared_type is None:
        declared_type = _infer_type(raw)
        if declared_type is None:
            raise NormalizationError(f"cannot infer type for: {raw!r}")

    if declared_type in (IocType.HASH_MD5, IocType.HASH_SHA1, IocType.HASH_SHA256):
        hashed_type, value = normalize_hash(raw)
        if hashed_type != declared_type:
            raise NormalizationError(
                f"declared {declared_type.value} but value is {hashed_type.value}"
            )
        ioc_type = declared_type
    elif declared_type == IocType.IP:
        value = normalize_ip(raw)
        ioc_type = IocType.IP
    elif declared_type == IocType.DOMAIN:
        value = normalize_domain(raw)
        ioc_type = IocType.DOMAIN
    elif declared_type == IocType.URL:
        value = normalize_url(raw)
        ioc_type = IocType.URL
    else:  # pragma: no cover - defensive
        raise NormalizationError(f"unsupported type: {declared_type}")

    return NormalizedIoc(
        type=ioc_type,
        value=value,
        raw_value=raw.strip(),
        fingerprint=compute_fingerprint(ioc_type, value),
    )


def _infer_type(raw: str) -> IocType | None:
    candidate = raw.strip()
    if candidate.lower().startswith(("http://", "https://")):
        return IocType.URL
    if re.fullmatch(r"[a-fA-F0-9]+", candidate) and len(candidate) in _HASH_TYPES_BY_LENGTH:
        return _HASH_TYPES_BY_LENGTH[len(candidate)]
    try:
        ipaddress.ip_address(candidate)
        return IocType.IP
    except ValueError:
        pass
    return None
