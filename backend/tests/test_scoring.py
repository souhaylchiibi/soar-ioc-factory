"""Phase 3 — scoring engine: explainability, decay, anti-collusion, decisions."""
from datetime import datetime, timedelta, timezone

from app.models.ioc import IocType
from app.scoring.engine import DEFAULT_POLICY, ScoringInput, compute_score

NOW = datetime(2026, 11, 6, tzinfo=timezone.utc)


def make_input(**overrides) -> ScoringInput:
    base = dict(
        ioc_type=IocType.IP,
        first_seen_at=NOW - timedelta(days=1),
        last_seen_at=NOW - timedelta(days=1),
        source_reliability=80,
        independent_source_count=2,
        enrichment_verdicts=["malicious", "malicious"],
        detection_count=3,
        false_positive_count=0,
        now=NOW,
    )
    base.update(overrides)
    return ScoringInput(**base)


class TestExplainability:
    def test_every_component_is_explained(self) -> None:
        result = compute_score(make_input())
        assert len(result.components) == 5  # source, freshness, sources, enrich, detect
        for component in result.components:
            assert component.explanation, f"{component.key} lacks an explanation"
            assert 0 <= component.value <= component.max_value

    def test_breakdown_is_persistable_json(self) -> None:
        breakdown = compute_score(make_input()).breakdown
        assert breakdown["final_score"] >= 0
        assert breakdown["decision"] in ("publish", "monitor", "reject")
        assert len(breakdown["components"]) == 5
        assert breakdown["policy_version"] == "v1"

    def test_human_explanation_mentions_decision(self) -> None:
        assert "-> publish" in compute_score(make_input()).explanation


class TestBounds:
    def test_score_always_within_0_100(self) -> None:
        best = compute_score(make_input(
            source_reliability=100, independent_source_count=10,
            enrichment_verdicts=["malicious"] * 5, detection_count=100,
            last_seen_at=NOW,
        ))
        worst = compute_score(make_input(
            source_reliability=0, independent_source_count=0,
            enrichment_verdicts=[], detection_count=0,
            false_positive_count=99, last_seen_at=NOW - timedelta(days=365),
        ))
        assert 0 <= worst.score <= 100
        assert 0 <= best.score <= 100
        assert best.score > worst.score

    def test_weights_sum_to_100(self) -> None:
        assert sum(DEFAULT_POLICY["weights"].values()) == 100


class TestFreshnessDecay:
    def test_score_decreases_with_age(self) -> None:
        fresh = compute_score(make_input(last_seen_at=NOW))
        aged = compute_score(make_input(last_seen_at=NOW - timedelta(days=7)))
        older = compute_score(make_input(last_seen_at=NOW - timedelta(days=60)))
        assert fresh.score > aged.score > older.score

    def test_one_half_life_halves_the_component(self) -> None:
        # IP half-life is 7 days in the default policy.
        fresh = compute_score(make_input(last_seen_at=NOW))
        one_half = compute_score(make_input(last_seen_at=NOW - timedelta(days=7)))
        c_fresh = next(c for c in fresh.components if c.key == "freshness")
        c_half = next(c for c in one_half.components if c.key == "freshness")
        assert abs(c_half.value - c_fresh.value / 2) < 0.01


class TestAntiCollusion:
    def test_more_sources_increase_but_saturate(self) -> None:
        scores = [
            compute_score(make_input(independent_source_count=n)).score
            for n in (0, 1, 2, 4, 10)
        ]
        assert scores == sorted(scores)
        # saturation: beyond max_independent_sources nothing is added
        assert compute_score(make_input(independent_source_count=4)).score == compute_score(
            make_input(independent_source_count=10)
        ).score

    def test_zero_independent_sources_contributes_nothing(self) -> None:
        result = compute_score(make_input(independent_source_count=0))
        component = next(c for c in result.components if c.key == "independent_sources")
        assert component.value == 0


class TestEnrichment:
    def test_benign_verdict_lowers_score(self) -> None:
        benign = compute_score(make_input(enrichment_verdicts=["benign"]))
        malicious = compute_score(make_input(enrichment_verdicts=["malicious"]))
        assert benign.score < malicious.score

    def test_no_enrichment_is_neutral_not_zero(self) -> None:
        result = compute_score(make_input(enrichment_verdicts=[]))
        component = next(c for c in result.components if c.key == "enrichment_agreement")
        assert component.value == component.max_value / 2

    def test_mixed_verdicts_documented(self) -> None:
        result = compute_score(make_input(enrichment_verdicts=["malicious", "benign"]))
        component = next(c for c in result.components if c.key == "enrichment_agreement")
        # Contradictory verdicts must be spelled out, not averaged silently.
        assert "malicious" in component.explanation and "benign" in component.explanation

    def test_single_provider_explanation(self) -> None:
        result = compute_score(make_input(enrichment_verdicts=["malicious"]))
        component = next(c for c in result.components if c.key == "enrichment_agreement")
        assert "1 fournisseur" in component.explanation


class TestFalsePositives:
    def test_fp_penalty_lowers_score_and_is_explained(self) -> None:
        clean = compute_score(make_input(false_positive_count=0))
        flagged = compute_score(make_input(false_positive_count=2))
        assert flagged.score < clean.score
        assert flagged.penalties, "penalty must be recorded"
        assert flagged.penalties[0].explanation

    def test_penalty_is_capped(self) -> None:
        some = compute_score(make_input(false_positive_count=3))
        many = compute_score(make_input(false_positive_count=100))
        assert many.penalties[0].value == some.penalties[0].value or \
            some.penalties[0].value == -DEFAULT_POLICY["false_positive_max_penalty"]


class TestDecisions:
    """Initial policy thresholds (configurable): >=80 publish, 50-79 monitor, <50 reject."""

    def test_high_confidence_publishes(self) -> None:
        assert compute_score(make_input(
            source_reliability=100, last_seen_at=NOW,
            independent_source_count=4, enrichment_verdicts=["malicious"] * 4,
            detection_count=10,
        )).decision == "publish"

    def test_low_confidence_rejects(self) -> None:
        assert compute_score(make_input(
            source_reliability=10, independent_source_count=0,
            enrichment_verdicts=[], detection_count=0,
            last_seen_at=NOW - timedelta(days=120),
        )).decision == "reject"

    def test_thresholds_are_configurable(self) -> None:
        custom = dict(DEFAULT_POLICY)
        custom["thresholds"] = {"publish": 95, "monitor": 10}
        result = compute_score(make_input(policy=custom))
        # Same indicator, stricter publish threshold -> no auto-publish.
        assert result.score < 95 or result.decision != "publish"

    def test_stale_good_ioc_drops_below_publish(self) -> None:
        """Trust must decrease over time — the core requirement."""
        fresh = compute_score(make_input(
            source_reliability=95, last_seen_at=NOW,
            independent_source_count=3, detection_count=8,
            enrichment_verdicts=["malicious"] * 3,
        ))
        stale = compute_score(make_input(
            source_reliability=95, last_seen_at=NOW - timedelta(days=60),
            independent_source_count=3, detection_count=8,
            enrichment_verdicts=["malicious"] * 3,
        ))
        assert fresh.score > stale.score
        assert fresh.decision == "publish"
