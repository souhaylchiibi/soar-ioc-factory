"""Users (auth) and generated reports."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, Date, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.ioc import ROLE_ENUM, RoleName


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)  # argon2
    role: Mapped[RoleName] = mapped_column(ROLE_ENUM, default=RoleName.viewer, server_default=sa_text("'viewer'"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=sa_text("TRUE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, server_default=sa_text("0"), nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False, default="daily", server_default=sa_text("'daily'"))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("report_date", "kind", name="uq_report_date_kind"),)
