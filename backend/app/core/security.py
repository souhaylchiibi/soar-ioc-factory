"""Authentication & authorization.

* Humans authenticate with username/password (Argon2id hashes) and receive a
  short-lived JWT (HS256, SECRET_KEY).
* Automation (n8n) authenticates with a service API key (header
  ``X-API-Key``); the comparison is constant-time and the key never appears
  in logs or responses.
* Roles are hierarchical: viewer < analyst < admin. The service principal
  has analyst rights (it runs pipeline operations, never manages users).

The acting identity always comes from the credential, never from the request
body: audit entries cannot be attributed to someone else.
"""
from __future__ import annotations

import hmac
import ipaddress
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.models.account import User
from app.models.ioc import RoleName

ALGORITHM = "HS256"
ROLE_RANK = {RoleName.viewer: 0, RoleName.analyst: 1, RoleName.admin: 2}

_hasher = PasswordHasher()  # Argon2id, library defaults (OWASP-compliant)


# ------------------------------------------------------------ passwords ----
def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


# Used to keep login timing constant when the username does not exist.
_DUMMY_HASH = _hasher.hash("timing-equaliser-not-a-password")


def verify_dummy() -> None:
    verify_password("x", _DUMMY_HASH)


def password_policy_error(password: str) -> Optional[str]:
    """Minimal policy: length + character classes. Returns None when OK."""
    if len(password) < 12:
        return "le mot de passe doit contenir au moins 12 caractères"
    classes = sum([
        any(c.islower() for c in password),
        any(c.isupper() for c in password),
        any(c.isdigit() for c in password),
        any(not c.isalnum() for c in password),
    ])
    if classes < 3:
        return "le mot de passe doit mélanger au moins 3 types de caractères"
    return None


# ----------------------------------------------------------------- tokens --
def create_access_token(user: User) -> tuple[str, datetime]:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user.id),
        "usr": user.username,
        "role": user.role.value,
        "exp": expires,
        "iat": datetime.now(timezone.utc),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM), expires


# -------------------------------------------------------------- principal --
@dataclass(frozen=True)
class Principal:
    """Who is calling. `actor` is what goes into audit/lifecycle records."""

    actor: str
    role: RoleName
    user_id: Optional[uuid.UUID] = None
    is_service: bool = False

    def has(self, minimum: RoleName) -> bool:
        return ROLE_RANK[self.role] >= ROLE_RANK[minimum]


_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Authentification requise",
    headers={"WWW-Authenticate": "Bearer"},
)


def _service_principal(request: Request) -> Optional[Principal]:
    key = request.headers.get("x-api-key")
    if not key:
        return None
    expected = settings.service_api_key
    if not expected or not hmac.compare_digest(key.encode(), expected.encode()):
        raise _UNAUTHORIZED
    # n8n may label itself (workflow-N) for traceability; the label is
    # restricted to a safe charset and always prefixed so it can't impersonate
    # a human account.
    label = request.headers.get("x-actor", "")
    if label and all(c.isalnum() or c in "-_/" for c in label) and len(label) <= 48:
        actor = label if label.startswith("workflow-") else f"service/{label}"
    else:
        actor = "service"
    return Principal(actor=actor, role=RoleName.analyst, is_service=True)


def get_principal(request: Request, db: Session = Depends(get_db)) -> Principal:
    """Resolve the caller from a Bearer JWT or the service API key."""
    if not settings.auth_enabled:
        # Explicit opt-out for local experiments only (refused in production).
        return Principal(actor="anonymous-dev", role=RoleName.admin)

    service = _service_principal(request)
    if service is not None:
        return service

    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise _UNAUTHORIZED
    token = header[7:].strip()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM],
                             options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        raise _UNAUTHORIZED from None

    try:
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError):
        raise _UNAUTHORIZED from None
    user = db.get(User, user_id)
    # Re-check the account on every request: disabling a user or changing
    # their role takes effect immediately, not at token expiry.
    if user is None or not user.is_active:
        raise _UNAUTHORIZED
    return Principal(actor=user.username, role=user.role, user_id=user.id)


def require_role(minimum: RoleName) -> Callable[..., Principal]:
    def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        if not principal.has(minimum):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"rôle {minimum.value} requis (rôle actuel : {principal.role.value})",
            )
        return principal

    return _dep


require_viewer = require_role(RoleName.viewer)
require_analyst = require_role(RoleName.analyst)
require_admin = require_role(RoleName.admin)


def client_ip(request: Request) -> Optional[str]:
    """Best-effort client IP (nginx sets X-Real-IP; only trusted behind it)."""
    real = request.headers.get("x-real-ip")
    candidate = real.strip() if real and settings.trust_proxy_headers else (
        request.client.host if request.client else None)
    # audit_logs.ip_address is INET: store only syntactically valid addresses
    # (a unix socket or test transport must not break the login path).
    try:
        return str(ipaddress.ip_address(candidate)) if candidate else None
    except ValueError:
        return None
