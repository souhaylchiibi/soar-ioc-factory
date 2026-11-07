"""ORM models for the IOC engine (Phase 3).

Mirrors database/schema.sql — Alembic migrations stay the source of truth
for the schema history; these classes are what the application queries.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, UUID
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


# ---------------------------------------------------------------- enums ----
class IocType(str, enum.Enum):
    IP = "IP"
    DOMAIN = "DOMAIN"
    URL = "URL"
    HASH_MD5 = "HASH_MD5"
    HASH_SHA1 = "HASH_SHA1"
    HASH_SHA256 = "HASH_SHA256"


class IocStatus(str, enum.Enum):
    NEW = "NEW"
    NORMALIZED = "NORMALIZED"
    ENRICHED = "ENRICHED"
    SCORED = "SCORED"
    PUBLISHED = "PUBLISHED"
    MONITORED = "MONITORED"
    EXPIRED = "EXPIRED"
    REMOVED = "REMOVED"
    REJECTED = "REJECTED"
    DUPLICATE = "DUPLICATE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SourceKind(str, enum.Enum):
    COMMERCIAL = "COMMERCIAL"
    COMMUNITY = "COMMUNITY"
    OPEN_SOURCE = "OPEN_SOURCE"
    INTERNAL = "INTERNAL"
    SYNTHETIC = "SYNTHETIC"


class RoleName(str, enum.Enum):
    admin = "admin"
    analyst = "analyst"
    viewer = "viewer"


# One shared Enum instance per type == one native PG type (as in schema.sql).
def _enum(cls: type[enum.Enum], name: str) -> Enum:
    return Enum(cls, name=name, native_enum=True, validate_strings=True, values_callable=lambda e: [m.value for m in e])


IOC_TYPE_ENUM = _enum(IocType, "ioc_type")
IOC_STATUS_ENUM = _enum(IocStatus, "ioc_status")
RISK_LEVEL_ENUM = _enum(RiskLevel, "risk_level")
SOURCE_KIND_ENUM = _enum(SourceKind, "source_kind")
ROLE_ENUM = _enum(RoleName, "role_name")


# -------------------------------------------------------------- sources ----
class IntelSource(Base):
    __tablename__ = "intel_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    url: Mapped[Optional[str]] = mapped_column(Text)
    kind: Mapped[SourceKind] = mapped_column(SOURCE_KIND_ENUM, default=SourceKind.OPEN_SOURCE, server_default=sa_text("'OPEN_SOURCE'"))
    # Several feeds echoing the same upstream share a provenance_group:
    # they count as ONE independent source (anti-collusion).
    provenance_group: Mapped[str] = mapped_column(String(120), nullable=False)
    reliability: Mapped[int] = mapped_column(SmallInteger, default=50, server_default=sa_text("50"), nullable=False)
    requires_api_key: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_text("FALSE"), nullable=False)
    rate_limit_rpm: Mapped[int] = mapped_column(Integer, default=60, server_default=sa_text("60"), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=sa_text("TRUE"), nullable=False)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_error_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("reliability >= 0 AND reliability <= 100", name="ck_source_reliability"),
    )


# ------------------------------------------------------------------ ioc ----
class Ioc(Base):
    __tablename__ = "iocs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    type: Mapped[IocType] = mapped_column(IOC_TYPE_ENUM, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    raw_value: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[IocStatus] = mapped_column(IOC_STATUS_ENUM, default=IocStatus.NEW, server_default=sa_text("'NEW'"), nullable=False)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    removed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    score: Mapped[Optional[int]] = mapped_column(SmallInteger)
    score_breakdown: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    scored_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    risk_level: Mapped[Optional[RiskLevel]] = mapped_column(RISK_LEVEL_ENUM)

    # Deterministic dedup key: hash(type + normalized value).
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    duplicate_of: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("iocs.id", ondelete="SET NULL"))

    detection_count: Mapped[int] = mapped_column(Integer, default=0, server_default=sa_text("0"), nullable=False)
    false_positive_count: Mapped[int] = mapped_column(Integer, default=0, server_default=sa_text("0"), nullable=False)
    last_detection_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_text("FALSE"), nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, server_default=sa_text("'{}'"), nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default=sa_text("'{}'"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_ioc_score"),
        Index("idx_iocs_status", "status"),
        Index("idx_iocs_type", "type"),
        Index("idx_iocs_expires_at", "expires_at"),
        Index("idx_iocs_score", "score"),
    )

    # relations
    source_links: Mapped[list["IocSource"]] = relationship(
        back_populates="ioc", cascade="all, delete-orphan", lazy="selectin"
    )
    enrichments: Mapped[list["Enrichment"]] = relationship(
        back_populates="ioc", cascade="all, delete-orphan", lazy="selectin"
    )
    lifecycle_events: Mapped[list["LifecycleEvent"]] = relationship(
        back_populates="ioc", cascade="all, delete-orphan", order_by="LifecycleEvent.created_at"
    )
    score_history: Mapped[list["ScoreHistory"]] = relationship(
        back_populates="ioc", cascade="all, delete-orphan", order_by="ScoreHistory.computed_at.desc()"
    )


class IocSource(Base):
    """Provenance link: which source reported this IOC and when."""

    __tablename__ = "ioc_sources"

    ioc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("iocs.id", ondelete="CASCADE"), primary_key=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intel_sources.id", ondelete="CASCADE"), primary_key=True
    )
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    external_id: Mapped[Optional[str]] = mapped_column(Text)
    external_url: Mapped[Optional[str]] = mapped_column(Text)

    ioc: Mapped[Ioc] = relationship(back_populates="source_links")
    source: Mapped[IntelSource] = relationship(lazy="joined")


# --------------------------------------------------------- enrichment ------
class Enrichment(Base):
    __tablename__ = "enrichments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    ioc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("iocs.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    verdict: Mapped[Optional[str]] = mapped_column(Text)
    reputation: Mapped[Optional[int]] = mapped_column(SmallInteger)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_text("FALSE"), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    ioc: Mapped[Ioc] = relationship(back_populates="enrichments")

    __table_args__ = (
        UniqueConstraint("ioc_id", "provider", "fetched_at", name="uq_enrichment_ioc_provider_time"),
        CheckConstraint("reputation >= -100 AND reputation <= 100", name="ck_enrichment_reputation"),
        Index("idx_enrichments_ioc", "ioc_id", "fetched_at"),
    )


# ------------------------------------------------------------- scoring -----
class ScoreHistory(Base):
    __tablename__ = "score_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    ioc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("iocs.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    risk_level: Mapped[Optional[RiskLevel]] = mapped_column(RISK_LEVEL_ENUM)
    breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    policy: Mapped[str] = mapped_column(Text, nullable=False, default="v1")
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    ioc: Mapped[Ioc] = relationship(back_populates="score_history")

    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_score_history_score"),
        Index("idx_score_history_ioc", "ioc_id", "computed_at"),
    )


class ScoringPolicy(Base):
    __tablename__ = "scoring_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    version: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_text("FALSE"), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("uq_single_active_policy", "active", unique=True, postgresql_where="active"),
    )


# ----------------------------------------------------------- lifecycle -----
class LifecycleEvent(Base):
    __tablename__ = "lifecycle_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    ioc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("iocs.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[Optional[IocStatus]] = mapped_column(IOC_STATUS_ENUM)
    to_status: Mapped[IocStatus] = mapped_column(IOC_STATUS_ENUM, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(Text, nullable=False, default="system", server_default=sa_text("'system'"))
    triggered_by: Mapped[Optional[str]] = mapped_column(Text)
    score_before: Mapped[Optional[int]] = mapped_column(SmallInteger)
    score_after: Mapped[Optional[int]] = mapped_column(SmallInteger)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_text("FALSE"), nullable=False)
    verification_detail: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    ioc: Mapped[Ioc] = relationship(back_populates="lifecycle_events")

    __table_args__ = (
        Index("idx_lifecycle_ioc", "ioc_id", "created_at"),
        Index("idx_lifecycle_state", "to_status", "created_at"),
    )


# ------------------------------------------------------- detection/audit ----
class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    ioc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("iocs.id", ondelete="CASCADE"), nullable=False
    )
    sensor: Mapped[str] = mapped_column(Text, nullable=False)
    rule_id: Mapped[Optional[str]] = mapped_column(Text)
    raw_event: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    matched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_false_positive: Mapped[Optional[bool]] = mapped_column(Boolean)
    reviewed_by: Mapped[Optional[str]] = mapped_column(Text)
    review_note: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        Index("idx_detections_ioc", "ioc_id", "matched_at"),
        Index("idx_detections_fp", "is_false_positive"),
    )


class AuditLog(Base):
    """Append-only audit trail (DB trigger forbids UPDATE/DELETE)."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[Optional[RoleName]] = mapped_column(ROLE_ENUM)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(Text)
    entity_id: Mapped[Optional[str]] = mapped_column(Text)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default=sa_text("'{}'"), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(INET)
    success: Mapped[bool] = mapped_column(Boolean, default=True, server_default=sa_text("TRUE"), nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        Index("idx_audit_time", "occurred_at"),
        Index("idx_audit_actor", "actor", "occurred_at"),
    )


class Publication(Base):
    __tablename__ = "publications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    ioc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("iocs.id", ondelete="CASCADE"), nullable=False
    )
    target: Mapped[str] = mapped_column(Text, nullable=False)
    target_ref: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending", server_default=sa_text("'pending'"))
    detail: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_publications_status", "status"),
        Index("idx_publications_ioc", "ioc_id", "published_at"),
    )
