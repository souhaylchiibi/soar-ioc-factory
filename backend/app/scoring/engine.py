"""Explainable, configurable scoring engine.

Design goals:
* every component returns a value AND a human-readable explanation,
* the whole breakdown is persisted (score_breakdown) so the dashboard can
  answer "why is this score 84?",
* freshness decays over time (half-life per IOC type),
* independent sources are counted by *provenance group*, not by raw feed
  count (two feeds echoing OTX = ONE source),
* thresholds live in configuration, never in code constants.

Formula (weights sum to 100 before penalties):

    score = w_source   * source_reliability
          + w_freshness* freshness(age)
          + w_multi    * independent_sources(n)
          + w_enrich   * enrichment_agreement
          + w_detect   * observed_detections
          - penalty_fp * known_false_positives
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from app.models.ioc import IocType

# ------------------------------------------------------------- defaults ----
# Versioned so score_history can record which policy produced a value.
DEFAULT_POLICY: dict[str, Any] = {
    "policy_version": "v1",
    "weights": {
        "source_reliability": 25,
        "freshness": 20,
        "independent_sources": 20,
        "enrichment_agreement": 20,
        "observed_detections": 15,
    },
    "false_positive_penalty": 20,   # points removed per known FP (capped below)
    "false_positive_max_penalty": 40,
    "half_life_days": {             # freshness half-life per type
        "IP": 7,
        "DOMAIN": 14,
        "URL": 3,
        "HASH_MD5": 30,
        "HASH_SHA1": 30,
        "HASH_SHA256": 60,
    },
    "max_independent_sources": 4,   # n beyond this adds nothing
    "detections_saturation": 5,     # detections needed for full marks
    "thresholds": {"publish": 80, "monitor": 50},
}


@dataclass
class Component:
    """One explainable piece of the final score."""

    key: str
    label: str
    value: float          # points actually contributed (may be 0..weight)
    max_value: float      # points available
    explanation: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "points": round(self.value, 2),
            "max_points": self.max_value,
            "explanation": self.explanation,
        }


@dataclass
class ScoreResult:
    score: int
    components: list[Component] = field(default_factory=list)
    penalties: list[Component] = field(default_factory=list)
    decision: str = ""          # publish | monitor | reject
    policy_version: str = "v1"

    @property
    def breakdown(self) -> dict[str, Any]:
        return {
            "policy_version": self.policy_version,
            "components": [c.as_dict() for c in self.components],
            "penalties": [c.as_dict() for c in self.penalties],
            "final_score": self.score,
            "decision": self.decision,
        }

    @property
    def explanation(self) -> str:
        parts = [f"{c.label}: +{c.value:.1f}/{c.max_value:.0f} ({c.explanation})" for c in self.components]
        parts += [f"{c.label}: {c.value:.1f} ({c.explanation})" for c in self.penalties]
        parts.append(f"final={self.score} -> {self.decision}")
        return " | ".join(parts)


@dataclass
class ScoringInput:
    """Everything the engine needs about one indicator."""

    ioc_type: IocType
    first_seen_at: datetime
    last_seen_at: datetime
    source_reliability: int                    # 0..100 (best source)
    independent_source_count: int              # distinct provenance groups
    enrichment_verdicts: list[str]             # e.g. ["malicious","suspicious"]
    detection_count: int
    false_positive_count: int
    now: datetime | None = None
    policy: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_POLICY))


# ------------------------------------------------------------ components ---
def _freshness_half_life(policy: dict, ioc_type: IocType) -> float:
    return float(policy["half_life_days"].get(ioc_type.value, 7))


def _freshness_score(age_days: float, half_life_days: float) -> float:
    """Exponential decay: 100 at age 0, 50 after one half-life, ..."""
    if age_days <= 0:
        return 100.0
    return 100.0 * (0.5 ** (age_days / half_life_days))


def _independent_sources_score(count: int, maximum: int) -> float:
    """Logarithmic: 1 source is already meaningful, extra sources saturate.

    Clamped at 100: `count > maximum` must not exceed the component's weight.
    """
    if count <= 0:
        return 0.0
    ratio = math.log(1 + count) / math.log(1 + maximum)
    return min(100.0, 100.0 * ratio)


def _enrichment_score(verdicts: list[str]) -> tuple[float, str]:
    """Consensus of enrichment verdicts -> 0..100 + explanation."""
    if not verdicts:
        return 50.0, "aucun enrichissement disponible — contribution neutre"
    weights = {"malicious": 100, "suspicious": 65, "unknown": 40, "benign": 0}
    values = [weights.get(v, 40) for v in verdicts]
    agreement = sum(values) / len(values)
    distinct = set(verdicts)
    if len(verdicts) == 1:
        note = f"1 fournisseur: '{verdicts[0]}'"
    elif len(distinct) == 1:
        note = f"{len(verdicts)} fournisseurs s'accordent sur '{verdicts[0]}'"
    else:
        note = f"verdicts partagés: {', '.join(verdicts)}"
    return float(agreement), note


def _detection_score(count: int, saturation: int) -> tuple[float, str]:
    if count <= 0:
        return 0.0, "no detection observed yet"
    value = 100.0 * min(1.0, math.log(1 + count) / math.log(1 + saturation))
    return value, f"{count} detection(s) observed"


def compute_score(inp: ScoringInput) -> ScoreResult:
    """Compute the score and its full explanation. Pure function — no I/O."""
    policy = inp.policy or DEFAULT_POLICY
    weights: dict[str, int] = policy["weights"]
    now = inp.now or datetime.now(timezone.utc)

    components: list[Component] = []

    # 1) Source reliability ------------------------------------------------
    reliability = max(0, min(100, inp.source_reliability))
    w = weights["source_reliability"]
    components.append(
        Component(
            key="source_reliability",
            label="Fiabilité de la source",
            value=w * reliability / 100.0,
            max_value=float(w),
            explanation=f"source score {reliability}/100",
        )
    )

    # 2) Freshness ---------------------------------------------------------
    w = weights["freshness"]
    age = max(0.0, (now - inp.last_seen_at).total_seconds() / 86400.0)
    half_life = _freshness_half_life(policy, inp.ioc_type)
    fres = _freshness_score(age, half_life)
    components.append(
        Component(
            key="freshness",
            label="Fraîcheur",
            value=w * fres / 100.0,
            max_value=float(w),
            explanation=f"age {age:.1f} j, demi-vie {half_life:.0f} j -> {fres:.0f}/100",
        )
    )

    # 3) Independent sources ----------------------------------------------
    w = weights["independent_sources"]
    max_src = int(policy["max_independent_sources"])
    multi = _independent_sources_score(inp.independent_source_count, max_src)
    components.append(
        Component(
            key="independent_sources",
            label="Sources indépendantes",
            value=w * multi / 100.0,
            max_value=float(w),
            explanation=(
                f"{inp.independent_source_count} groupe(s) de provenance distinct(s) "
                f"(anti-collusion, max {max_src})"
            ),
        )
    )

    # 4) Enrichment agreement ---------------------------------------------
    w = weights["enrichment_agreement"]
    enr, enr_note = _enrichment_score(inp.enrichment_verdicts)
    components.append(
        Component(
            key="enrichment_agreement",
            label="Consensus d'enrichissement",
            value=w * enr / 100.0,
            max_value=float(w),
            explanation=enr_note,
        )
    )

    # 5) Observed detections ----------------------------------------------
    w = weights["observed_detections"]
    det, det_note = _detection_score(inp.detection_count, int(policy["detections_saturation"]))
    components.append(
        Component(
            key="observed_detections",
            label="Détections observées",
            value=w * det / 100.0,
            max_value=float(w),
            explanation=det_note,
        )
    )

    raw = sum(c.value for c in components)

    # Penalties ------------------------------------------------------------
    penalties: list[Component] = []
    if inp.false_positive_count > 0:
        per_fp = float(policy["false_positive_penalty"])
        max_pen = float(policy["false_positive_max_penalty"])
        penalty = min(inp.false_positive_count * per_fp, max_pen)
        penalties.append(
            Component(
                key="false_positives",
                label="Faux positifs connus",
                value=-penalty,
                max_value=0.0,
                explanation=(
                    f"{inp.false_positive_count} faux positif(s) x {per_fp:.0f} pts "
                    f"(plafond {max_pen:.0f})"
                ),
            )
        )

    final = max(0, min(100, round(raw + sum(p.value for p in penalties))))

    # Decision -------------------------------------------------------------
    thresholds = policy["thresholds"]
    if final >= thresholds["publish"]:
        decision = "publish"
    elif final >= thresholds["monitor"]:
        decision = "monitor"
    else:
        decision = "reject"

    return ScoreResult(
        score=final,
        components=components,
        penalties=penalties,
        decision=decision,
        policy_version=str(policy.get("policy_version", "v1")),
    )
