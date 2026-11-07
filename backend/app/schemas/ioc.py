"""Pydantic schemas — request/response contracts for the IOC API."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.ioc import IocStatus, IocType, RiskLevel


# ------------------------------------------------------------ ingest -------
class IngestItem(BaseModel):
    """One raw indicator submitted by a collector or a workflow."""

    value: str = Field(..., min_length=1, max_length=2048,
                       description="Valeur brute telle que reçue de la source")
    type: Optional[IocType] = Field(None, description="Type déclaré ; inféré si absent")
    source: str = Field(..., min_length=1, max_length=120, description="Nom de la source")
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    tags: list[str] = Field(default_factory=list)
    external_id: Optional[str] = None
    external_url: Optional[str] = None
    is_synthetic: bool = False


class IngestRequest(BaseModel):
    items: list[IngestItem] = Field(..., min_length=1, max_length=500)


class IngestResult(BaseModel):
    raw_value: str
    action: str  # created | updated | duplicate | rejected
    ioc_id: Optional[str] = None
    reason: str = ""


class IngestResponse(BaseModel):
    created: int = 0
    updated: int = 0
    duplicates: int = 0
    rejected: int = 0
    results: list[IngestResult]


# ------------------------------------------------------------- ioc view ----
class ScoreComponentOut(BaseModel):
    key: str
    label: str
    points: float
    max_points: float
    explanation: str


class ScoreOut(BaseModel):
    score: int
    risk_level: Optional[RiskLevel] = None
    policy_version: Optional[str] = None
    components: list[ScoreComponentOut] = Field(default_factory=list)
    penalties: list[ScoreComponentOut] = Field(default_factory=list)
    decision: Optional[str] = None


class SourceLinkOut(BaseModel):
    name: str
    provenance_group: str
    reliability: int
    external_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class LifecycleEventOut(BaseModel):
    from_status: Optional[IocStatus]
    to_status: IocStatus
    reason: str
    actor: str
    triggered_by: Optional[str] = None
    score_before: Optional[int] = None
    score_after: Optional[int] = None
    verified: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IocOut(BaseModel):
    id: uuid.UUID
    type: IocType
    value: str
    raw_value: str
    status: IocStatus
    score: Optional[int] = None
    risk_level: Optional[RiskLevel] = None
    first_seen_at: datetime
    last_seen_at: datetime
    expires_at: Optional[datetime] = None
    removed_at: Optional[datetime] = None
    detection_count: int
    false_positive_count: int
    is_synthetic: bool
    tags: list[str]
    independent_source_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class IocDetail(IocOut):
    score_breakdown: Optional[dict[str, Any]] = None
    context: dict[str, Any] = Field(default_factory=dict)
    sources: list[SourceLinkOut] = Field(default_factory=list)
    lifecycle: list[LifecycleEventOut] = Field(default_factory=list)
    enrichment_verdicts: list[str] = Field(default_factory=list)


class IocListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[IocOut]


# ------------------------------------------------------------- actions -----
class TransitionRequest(BaseModel):
    to_status: IocStatus
    reason: str = Field(..., min_length=3, max_length=500)
    actor: str = "operator"
    verified: bool = False


class ScoringRunRequest(BaseModel):
    """Score a set of IOCs (used by n8n workflow 4)."""

    ioc_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    only_status: Optional[IocStatus] = Field(
        IocStatus.ENRICHED, description="Restreindre à un statut (ex. ENRICHED)"
    )


class ScoringRunResponse(BaseModel):
    scored: int = 0
    published: int = 0
    monitored: int = 0
    rejected: int = 0
    details: list[dict[str, Any]] = Field(default_factory=list)


# -------------------------------------------------------------- stats ------
class DashboardStats(BaseModel):
    total_iocs: int
    active_iocs: int
    expired_iocs: int
    rejected_iocs: int
    removed_iocs: int
    review_required: int
    published_iocs: int
    monitored_iocs: int
    duplicates_seen: int
    synthetic_iocs: int
    false_positives: int
    total_detections: int
    avg_score: Optional[float] = None
    avg_processing_seconds: Optional[float] = None
    dedup_rate: Optional[float] = None
    by_type: dict[str, int]
    by_status: dict[str, int]
    by_risk: dict[str, int]
    score_distribution: dict[str, int]
    daily_new: list[dict[str, Any]] = Field(default_factory=list)


class SourceStat(BaseModel):
    name: str
    provenance_group: str
    reliability: int
    enabled: bool
    ioc_count: int
    last_success_at: Optional[datetime] = None
    last_error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
