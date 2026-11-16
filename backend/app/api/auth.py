"""Authentication and user administration.

Every login attempt (success or failure) and every account change is written
to the append-only audit trail with the client IP.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.core.security import (
    Principal,
    client_ip,
    create_access_token,
    get_principal,
    hash_password,
    password_policy_error,
    require_admin,
    verify_dummy,
    verify_password,
)
from app.models.account import User
from app.models.ioc import AuditLog, RoleName

logger = get_logger("soar.api.auth")
router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: "UserOut"


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    role: RoleName
    is_active: bool
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    locked_until: Optional[datetime] = None

    model_config = {"from_attributes": True}


class MeOut(BaseModel):
    actor: str
    role: RoleName
    is_service: bool
    user: Optional[UserOut] = None


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9._-]+$")
    email: str = Field(..., min_length=3, max_length=200, pattern=r"^[^@\s]+@[^@\s]+$")
    password: str = Field(..., min_length=12, max_length=256)
    role: RoleName = RoleName.analyst


class UserUpdate(BaseModel):
    role: Optional[RoleName] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=12, max_length=256)


TokenResponse.model_rebuild()


def _audit(db: Session, request: Request, actor: str, action: str, success: bool,
           role: Optional[RoleName] = None, entity_id: Optional[str] = None,
           detail: Optional[dict] = None, error: Optional[str] = None) -> None:
    db.add(AuditLog(
        actor=actor, role=role, action=action, entity_type="user", entity_id=entity_id,
        detail=detail or {}, ip_address=client_ip(request), success=success, error=error,
    ))


# ------------------------------------------------------------------ login --
@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    generic = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Identifiants invalides")
    user = db.execute(select(User).where(User.username == body.username)).scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if user is None:
        verify_dummy()  # same cost as a real check: no username enumeration by timing
        _audit(db, request, body.username[:64], "LOGIN", False, error="unknown user")
        db.commit()
        raise generic

    if user.locked_until and user.locked_until > now:
        _audit(db, request, user.username, "LOGIN", False, role=user.role,
               entity_id=str(user.id), error="account locked")
        db.commit()
        raise HTTPException(status_code=status.HTTP_423_LOCKED,
                            detail="Compte temporairement verrouillé après plusieurs échecs")

    if not user.is_active or not verify_password(body.password, user.password_hash):
        user.failed_logins = (user.failed_logins or 0) + 1
        detail = {"failed_logins": user.failed_logins}
        if user.failed_logins >= settings.login_max_failures:
            user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
            detail["locked_until"] = user.locked_until.isoformat()
        _audit(db, request, user.username, "LOGIN", False, role=user.role,
               entity_id=str(user.id), detail=detail,
               error="inactive account" if not user.is_active else "bad password")
        db.commit()
        raise generic

    user.failed_logins = 0
    user.locked_until = None
    user.last_login_at = now
    token, expires = create_access_token(user)
    _audit(db, request, user.username, "LOGIN", True, role=user.role, entity_id=str(user.id))
    db.commit()
    return TokenResponse(access_token=token, expires_at=expires, user=UserOut.model_validate(user))


@router.get("/me", response_model=MeOut)
def me(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> MeOut:
    user = db.get(User, principal.user_id) if principal.user_id else None
    return MeOut(actor=principal.actor, role=principal.role, is_service=principal.is_service,
                 user=UserOut.model_validate(user) if user else None)


@router.post("/logout", status_code=204, response_class=Response, response_model=None)
def logout(request: Request, principal: Principal = Depends(get_principal),
           db: Session = Depends(get_db)) -> Response:
    """Stateless JWT: the client drops the token; we keep the trace."""
    _audit(db, request, principal.actor, "LOGOUT", True, role=principal.role,
           entity_id=str(principal.user_id) if principal.user_id else None)
    db.commit()
    return Response(status_code=204)


# ------------------------------------------------------------ user admin --
@users_router.get("", response_model=list[UserOut])
def list_users(_: Principal = Depends(require_admin), db: Session = Depends(get_db)) -> list[UserOut]:
    rows = db.execute(select(User).order_by(User.created_at)).scalars().all()
    return [UserOut.model_validate(u) for u in rows]


@users_router.post("", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, request: Request,
                principal: Principal = Depends(require_admin),
                db: Session = Depends(get_db)) -> UserOut:
    if (err := password_policy_error(body.password)) is not None:
        raise HTTPException(status_code=422, detail=err)
    clash = db.execute(select(User).where(
        (User.username == body.username) | (User.email == body.email))).scalar_one_or_none()
    if clash is not None:
        raise HTTPException(status_code=409, detail="nom d'utilisateur ou e-mail déjà utilisé")
    user = User(username=body.username, email=body.email,
                password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    db.flush()
    _audit(db, request, principal.actor, "USER_CREATE", True, role=principal.role,
           entity_id=str(user.id), detail={"username": user.username, "role": user.role.value})
    db.commit()
    return UserOut.model_validate(user)


@users_router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: uuid.UUID, body: UserUpdate, request: Request,
                principal: Principal = Depends(require_admin),
                db: Session = Depends(get_db)) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="utilisateur introuvable")

    changes: dict = {}
    demoting_self = principal.user_id == user.id and (
        (body.role is not None and body.role != RoleName.admin) or body.is_active is False)
    if demoting_self:
        raise HTTPException(status_code=409,
                            detail="un administrateur ne peut pas se rétrograder ou se désactiver lui-même")

    if body.role is not None and body.role != user.role:
        if user.role == RoleName.admin and body.role != RoleName.admin:
            _ensure_other_admin(db, user)
        changes["role"] = {"from": user.role.value, "to": body.role.value}
        user.role = body.role
    if body.is_active is not None and body.is_active != user.is_active:
        if not body.is_active and user.role == RoleName.admin:
            _ensure_other_admin(db, user)
        changes["is_active"] = {"from": user.is_active, "to": body.is_active}
        user.is_active = body.is_active
    if body.password is not None:
        if (err := password_policy_error(body.password)) is not None:
            raise HTTPException(status_code=422, detail=err)
        user.password_hash = hash_password(body.password)
        user.failed_logins = 0
        user.locked_until = None
        changes["password"] = "reset"  # nosec B105 - audit label, the value is never logged
    if not changes:
        raise HTTPException(status_code=400, detail="aucune modification fournie")

    _audit(db, request, principal.actor, "USER_UPDATE", True, role=principal.role,
           entity_id=str(user.id), detail={"username": user.username, "changes": changes})
    db.commit()
    return UserOut.model_validate(user)


def _ensure_other_admin(db: Session, user: User) -> None:
    others = db.execute(select(func.count(User.id)).where(
        User.role == RoleName.admin, User.is_active.is_(True), User.id != user.id)).scalar() or 0
    if others == 0:
        raise HTTPException(status_code=409, detail="impossible : ce serait le dernier administrateur actif")


# -------------------------------------------------------------- bootstrap --
def bootstrap_admin(db: Session) -> Optional[str]:
    """Create the first admin from ADMIN_PASSWORD when no user exists.

    Returns the username created, or None. Never logs the password.
    """
    if not settings.admin_password:
        return None
    if (db.execute(select(func.count(User.id))).scalar() or 0) > 0:
        return None
    if (err := password_policy_error(settings.admin_password)) is not None:
        logger.error("ADMIN_PASSWORD rejected by policy", extra={"action": "bootstrap"})
        raise RuntimeError(f"ADMIN_PASSWORD invalide : {err}")
    user = User(username=settings.admin_username, email=settings.admin_email,
                password_hash=hash_password(settings.admin_password), role=RoleName.admin)
    db.add(user)
    db.flush()
    db.add(AuditLog(actor="system", action="USER_CREATE", entity_type="user",
                    entity_id=str(user.id),
                    detail={"username": user.username, "role": "admin", "origin": "bootstrap"}))
    db.commit()
    return user.username
