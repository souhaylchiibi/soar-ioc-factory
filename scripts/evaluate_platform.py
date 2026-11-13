"""Phase 7 - Evaluation of the IOC factory, computed from the live database.

Design rules (same as the rest of the project):
* every number is read from PostgreSQL - nothing is invented;
* when a metric cannot be measured, it is reported as null with a reason;
* the "manual process" baseline is an EXPLICIT model (documented unit times),
  never presented as a measurement. It lives in MANUAL_BASELINE and every
  output that uses it is labelled as a hypothesis.

Outputs
-------
reports/evaluation/metrics.json     machine-readable metrics
reports/evaluation/EVALUATION.md    human-readable report (French)
reports/figures/*.png               charts used by the Word report

Usage
-----
    python scripts/evaluate_platform.py
    python scripts/evaluate_platform.py --no-charts
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = ROOT / "reports" / "evaluation" / "metrics.json"
DEFAULT_MD = ROOT / "reports" / "evaluation" / "EVALUATION.md"
DEFAULT_FIGS = ROOT / "reports" / "figures"

# --------------------------------------------------------------------------
# Manual process baseline - HYPOTHESIS, not a measurement.
# Unit times come from a documented, deliberately conservative analyst model
# (one analyst, no automation, one indicator at a time). They are listed here
# so the jury can challenge them: change a number and re-run the script.
# --------------------------------------------------------------------------
MANUAL_BASELINE: dict[str, Any] = {
    "label": "Modele de reference manuel (HYPOTHESE, non mesure)",
    "unit_minutes_per_ioc": {
        "collecte_et_verification_source": 1.0,
        "normalisation_et_validation": 2.0,
        "recherche_de_doublons": 2.0,
        "enrichissement_2_sources": 4.0,
        "notation_et_decision": 3.0,
        "publication_et_verification": 4.0,
        "journalisation_et_tracabilite": 1.0,
    },
    "note": (
        "Temps unitaires par indicateur pour un analyste SOC sans automatisation. "
        "Modele explicite servant de point de comparaison : ce n'est PAS une mesure "
        "du passe. Les chiffres automatises, eux, viennent tous de la base."
    ),
}


# ------------------------------------------------------------------- utils --
def load_dotenv() -> None:
    """Read .env when the variables are not already exported (Windows dev)."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def db_engine():
    load_dotenv()
    password = os.environ.get("POSTGRES_PASSWORD", "")
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = os.environ.get("POSTGRES_USER", "soar")
    database = os.environ.get("POSTGRES_DB", "soar_ioc")
    return create_engine(
        f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}",
        pool_pre_ping=True,
        future=True,
    )


def pct(part: float, whole: float) -> Optional[float]:
    return round(part / whole * 100, 1) if whole else None


def quantile(values: list[float], q: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[idx]


# ------------------------------------------------------------------ collect --
def collect_metrics(engine) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    m: dict[str, Any] = {
        "generated_at": now.isoformat(),
        "database": engine.url.database,
        "inventory": {},
        "dedup": {},
        "enrichment": {},
        "scoring": {},
        "publication": {},
        "detection": {},
        "lifecycle": {},
        "performance": {},
        "audit": {},
        "sources": [],
        "automation": {},
        "notes": [],
    }

    with engine.connect() as conn:
        def rows(sql: str) -> list[tuple]:
            return list(conn.execute(text(sql)).all())

        def one(sql: str) -> Any:
            r = conn.execute(text(sql)).scalar()
            return r

        # ---------------------------------------------------------- inventory
        by_status = {r[0]: int(r[1]) for r in rows("select status, count(*) from iocs group by status")}
        by_type = {r[0]: int(r[1]) for r in rows("select type, count(*) from iocs group by type")}
        by_risk = {r[0]: int(r[1]) for r in rows(
            "select risk_level, count(*) from iocs where risk_level is not null group by risk_level")}
        total = int(one("select count(*) from iocs") or 0)
        m["inventory"] = {
            "total_iocs": total,
            "by_status": by_status,
            "by_type": by_type,
            "by_risk": by_risk,
            "synthetic_iocs": int(one("select count(*) from iocs where is_synthetic") or 0),
            "with_duplicate_of": int(one("select count(*) from iocs where duplicate_of is not null") or 0),
            "with_expiry": int(one("select count(*) from iocs where expires_at is not null") or 0),
        }

        # --------------------------------------------------------------- dedup
        dedup_events = int(one("select count(*) from audit_logs where action='DEDUP'") or 0)
        normalize_events = int(one("select count(*) from audit_logs where action='NORMALIZE'") or 0)
        collected = int(one("""
            select coalesce(sum((detail->>'collected')::int), 0) from audit_logs
            where action='COLLECT' and success and (detail->>'collected') is not null
        """) or 0)
        created = int(one("""
            select coalesce(sum((detail->>'created')::int), 0) from audit_logs
            where action='COLLECT' and success and (detail->>'created') is not null
        """) or 0)
        updated = int(one("""
            select coalesce(sum((detail->>'updated')::int), 0) from audit_logs
            where action='COLLECT' and success and (detail->>'updated') is not null
        """) or 0)
        collector_dups = int(one("""
            select coalesce(sum((detail->>'duplicates')::int), 0) from audit_logs
            where action='COLLECT' and success and (detail->>'duplicates') is not null
        """) or 0)
        rejected_input = int(one("""
            select coalesce(sum((detail->>'rejected')::int), 0) from audit_logs
            where action='COLLECT' and success and (detail->>'rejected') is not null
        """) or 0)
        m["dedup"] = {
            "raw_items_collected": collected,
            "created": created,
            "updated": updated,
            "duplicates_dropped_at_ingest": collector_dups,
            "invalid_rejected": rejected_input,
            "dedup_events": dedup_events,
            "normalize_events": normalize_events,
            # platform definition: DEDUP / (NORMALIZE + DEDUP)
            "dedup_rate_pct": pct(dedup_events, normalize_events + dedup_events),
            "duplicate_rate_of_inventory_pct": pct(m["inventory"]["with_duplicate_of"], total),
        }

        # ---------------------------------------------------------- enrichment
        enr_total = int(one("select count(*) from enrichments") or 0)
        enr_iocs = int(one("select count(distinct ioc_id) from enrichments") or 0)
        enr_errors = int(one("select count(*) from enrichments where (data->>'error') is not null") or 0)
        by_provider = {r[0]: int(r[1]) for r in rows(
            "select provider, count(*) from enrichments group by provider")}
        by_verdict = {f"{r[0]}/{r[1]}": int(r[2]) for r in rows(
            "select provider, verdict, count(*) from enrichments group by provider, verdict")}
        m["enrichment"] = {
            "results": enr_total,
            "iocs_enriched": enr_iocs,
            "coverage_pct": pct(enr_iocs, total),
            "provider_errors": enr_errors,
            "provider_success_pct": pct(enr_total - enr_errors, enr_total),
            "avg_results_per_enriched_ioc": round(enr_total / enr_iocs, 2) if enr_iocs else None,
            "by_provider": by_provider,
            "by_verdict": by_verdict,
        }

        # ------------------------------------------------------------- scoring
        scores = [float(r[0]) for r in rows("select score from iocs where score is not null")]
        breakdowns = [r[0] for r in rows("select score_breakdown from iocs where score_breakdown is not null")]
        buckets = {"0-49 (rejet)": 0, "50-64 (surveillance)": 0, "65-79 (surveillance)": 0,
                   "80-89 (publication)": 0, "90-100 (publication)": 0}
        for s in scores:
            if s < 50:
                buckets["0-49 (rejet)"] += 1
            elif s < 65:
                buckets["50-64 (surveillance)"] += 1
            elif s < 80:
                buckets["65-79 (surveillance)"] += 1
            elif s < 90:
                buckets["80-89 (publication)"] += 1
            else:
                buckets["90-100 (publication)"] += 1

        component_totals: dict[str, dict[str, float]] = {}
        for b in breakdowns:
            for comp in (b or {}).get("components", []):
                slot = component_totals.setdefault(
                    comp["key"], {"label": comp["label"], "points": 0.0,
                                  "max_points": float(comp["max_points"]), "n": 0})
                slot["points"] += float(comp["points"])
                slot["n"] += 1
        components = [
            {"key": k, "label": v["label"],
             "avg_points": round(v["points"] / v["n"], 2) if v["n"] else None,
             "max_points": v["max_points"],
             "avg_pct_of_max": round(v["points"] / v["n"] / v["max_points"] * 100, 1) if v["n"] and v["max_points"] else None}
            for k, v in component_totals.items()
        ]
        decisions = {
            "publish": int(one("select count(*) from iocs where status='PUBLISHED'") or 0),
            "monitor": int(one("select count(*) from iocs where status='MONITORED'") or 0),
            "reject": int(one("select count(*) from iocs where status='REJECTED'") or 0),
        }
        scored_total = len(scores)
        m["scoring"] = {
            "scored_iocs": scored_total,
            "coverage_pct": pct(scored_total, total),
            "avg": round(statistics.mean(scores), 1) if scores else None,
            "median": round(statistics.median(scores), 1) if scores else None,
            "p95": round(quantile(scores, 0.95) or 0, 1) if scores else None,
            "min": min(scores) if scores else None,
            "max": max(scores) if scores else None,
            "distribution": buckets,
            "decisions": decisions,
            "decisions_pct": {k: pct(v, scored_total) for k, v in decisions.items()},
            "explainable_iocs": len(breakdowns),
            "explainability_pct": pct(len(breakdowns), scored_total),
            "components_avg": sorted(components, key=lambda c: c["key"]),
            "policy": one("select policy from score_history order by computed_at desc limit 1") or "v1",
        }

        # --------------------------------------------------------- publication
        pubs = rows("""
            select target, status, count(*), count(revoked_at)
            from publications group by target, status
        """)
        pub_total = int(one("select count(*) from publications") or 0)
        pub_verified = int(one("select count(*) from publications where status='verified'") or 0)
        pub_revoked = int(one("select count(*) from publications where revoked_at is not null") or 0)
        m["publication"] = {
            "total": pub_total,
            "verified": pub_verified,
            "revoked": pub_revoked,
            "active": int(one("select count(*) from publications where revoked_at is null") or 0),
            "by_target_status": [{"target": r[0], "status": r[1], "count": int(r[2])} for r in pubs],
            "published_iocs": int(one("select count(*) from iocs where status='PUBLISHED'") or 0),
        }

        # ----------------------------------------------------------- detection
        det_total = int(one("select count(*) from detections") or 0)
        det_iocs = int(one("select count(distinct ioc_id) from detections") or 0)
        det_fp = int(one("select count(*) from detections where is_false_positive is true") or 0)
        m["detection"] = {
            "total": det_total,
            "iocs_with_detections": det_iocs,
            "coverage_pct": pct(det_iocs, total),
            "false_positives": det_fp,
            "false_positive_rate_pct": pct(det_fp, det_total),
            "by_sensor": {r[0]: int(r[1]) for r in rows(
                "select sensor, count(*) from detections group by sensor order by 2 desc")},
        }

        # ----------------------------------------------------------- lifecycle
        transitions = rows("""
            select to_status, count(*) from lifecycle_events group by to_status
        """)
        funnel = {r[0]: int(r[1]) for r in transitions}
        stage_rows = rows("""
            select to_status, seconds from (
              select le.to_status,
                     extract(epoch from (le.created_at - coalesce(prev.created_at, i.created_at))) seconds
              from lifecycle_events le
              join iocs i on i.id = le.ioc_id
              left join lateral (
                select created_at from lifecycle_events p
                where p.ioc_id = le.ioc_id and p.created_at < le.created_at
                order by p.created_at desc limit 1) prev on true
            ) t
        """)
        stages: dict[str, dict[str, Any]] = {}
        for status, seconds in stage_rows:
            if seconds is None:
                continue
            s = float(seconds)
            slot = stages.setdefault(status, {"all": [], "hot": []})
            slot["all"].append(s)
            if 0 <= s <= 3600:
                slot["hot"].append(s)
        lifecycle_stages = []
        for status, slot in stages.items():
            lifecycle_stages.append({
                "stage": status,
                "observed": len(slot["all"]),
                "avg_seconds_all": round(statistics.mean(slot["all"]), 2) if slot["all"] else None,
                "avg_seconds_hot": round(statistics.mean(slot["hot"]), 2) if slot["hot"] else None,
                "max_seconds": round(max(slot["all"]), 2) if slot["all"] else None,
            })
        full_cycle = rows("""
            select value, created_at, removed_at,
                   extract(epoch from (removed_at - created_at)) seconds,
                   (select count(*) from lifecycle_events le where le.ioc_id = i.id) transitions
            from iocs i where status='REMOVED' and removed_at is not null
            order by removed_at desc
        """)
        m["lifecycle"] = {
            "transitions_total": int(one("select count(*) from lifecycle_events") or 0),
            "by_target_status": funnel,
            "stages": sorted(lifecycle_stages, key=lambda x: -x["observed"]),
            "full_cycles": [{"value": r[0], "seconds": round(float(r[3]), 1),
                             "transitions": int(r[4])} for r in full_cycle],
            "expired": int(one("select count(*) from iocs where status='EXPIRED'") or 0),
            "removed": int(one("select count(*) from iocs where status='REMOVED'") or 0),
        }

        # --------------------------------------------------------- performance
        latency_rows = rows("""
            select extract(epoch from (min(sh.computed_at) - i.created_at)) seconds
            from iocs i join score_history sh on sh.ioc_id = i.id
            group by i.id
        """)
        all_lat = [float(r[0]) for r in latency_rows if r[0] is not None]
        hot_lat = [x for x in all_lat if 0 <= x <= 3600]
        cold_lat = [x for x in all_lat if x > 3600]
        m["performance"] = {
            "iocs_with_latency": len(all_lat),
            # "hot" = indicator processed within the same run (steady state)
            "hot_latency_iocs": len(hot_lat),
            "hot_latency_avg_s": round(statistics.mean(hot_lat), 1) if hot_lat else None,
            "hot_latency_max_s": round(max(hot_lat), 1) if hot_lat else None,
            # "cold" = backlog processed after the platform was stopped
            "backlog_iocs": len(cold_lat),
            "backlog_latency_avg_h": round(statistics.mean(cold_lat) / 3600, 1) if cold_lat else None,
            "backlog_note": (
                "Les indicateurs 'backlog' ont ete notations apres un arret volontaire de la "
                "plateforme (07/11 -> 14/11) : ce delai mesure l'indisponibilite, pas la performance."
            ) if cold_lat else None,
        }
        if hot_lat:
            # throughput observed during the hot batch (sequential processing)
            m["performance"]["hot_batch_throughput_ioc_per_s"] = round(len(hot_lat) / statistics.mean(hot_lat), 2)
            m["performance"]["hot_batch_iocs"] = len(hot_lat)

        # --------------------------------------------------------------- audit
        actions = rows("select action, count(*) from audit_logs group by action order by 2 desc")
        m["audit"] = {
            "events": int(one("select count(*) from audit_logs") or 0),
            "failed": int(one("select count(*) from audit_logs where not success") or 0),
            "by_action": {r[0]: int(r[1]) for r in actions},
        }

        # -------------------------------------------------------------- sources
        for name, kind, enabled, reliability, n in rows("""
            select s.name, s.kind, s.enabled, s.reliability, count(x.ioc_id)
            from intel_sources s left join ioc_sources x on x.source_id = s.id
            group by s.name, s.kind, s.enabled, s.reliability order by 5 desc
        """):
            m["sources"].append({"name": name, "kind": kind, "enabled": bool(enabled),
                                 "reliability": int(reliability), "ioc_count": int(n)})

    # ------------------------------------------------------------- scoring CPU
    m["performance"]["scoring_engine"] = benchmark_scoring_engine()

    # --------------------------------------------------------------- automation
    manual_min = sum(MANUAL_BASELINE["unit_minutes_per_ioc"].values())
    hot_s = m["performance"]["hot_latency_avg_s"]
    auto_min = round(hot_s / 60, 2) if hot_s else None
    total = m["inventory"]["total_iocs"]
    m["automation"] = {
        "manual_baseline": MANUAL_BASELINE,
        "manual_minutes_per_ioc": manual_min,
        "automated_minutes_per_ioc": auto_min,
        "time_reduction_factor": round(manual_min / auto_min, 1) if auto_min else None,
        "manual_hours_for_inventory": round(manual_min * total / 60, 1),
        "automated_hours_for_inventory": round((auto_min or 0) * total / 60, 2) if auto_min else None,
        "hours_saved_for_inventory": round(manual_min * total / 60 - (auto_min or 0) * total / 60, 1) if auto_min else None,
        "steps_automated": [
            "collecte multi-sources (4 collecteurs actifs)",
            "normalisation + validation + dedup par empreinte",
            "enrichissement OTX / AbuseIPDB avec cache 24 h",
            "notation explicable 5 composantes + anti-collusion",
            "decision automatique (publier / surveiller / rejeter)",
            "publication verifiee par relecture",
            "expiration puis retrait verifie",
            "journal d'audit append-only",
        ],
    }
    return m


def benchmark_scoring_engine(iterations: int = 5000) -> dict[str, Any]:
    """Pure-CPU throughput of the scoring engine (no DB, no network)."""
    try:
        sys.path.insert(0, str(ROOT / "backend"))
        from datetime import datetime, timedelta, timezone

        from app.models.ioc import IocType
        from app.scoring.engine import ScoringInput, compute_score

        now = datetime.now(timezone.utc)
        inp = ScoringInput(
            ioc_type=IocType.DOMAIN,
            first_seen_at=now - timedelta(hours=6),
            last_seen_at=now,
            source_reliability=75,
            independent_source_count=2,
            enrichment_verdicts=["malicious", "suspicious"],
            detection_count=3,
            false_positive_count=0,
        )
        start = time.perf_counter()
        for _ in range(iterations):
            compute_score(inp)
        elapsed = time.perf_counter() - start
        return {
            "iterations": iterations,
            "total_ms": round(elapsed * 1000, 1),
            "us_per_score": round(elapsed / iterations * 1_000_000, 1),
            "scores_per_second": round(iterations / elapsed, 0),
        }
    except Exception as exc:  # pragma: no cover - benchmark is best effort
        return {"error": f"{type(exc).__name__}: {exc}"}


# ------------------------------------------------------------------ charts --
def make_charts(m: dict[str, Any], out: Path) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator

    out.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.edgecolor": "#d0d7de",
        "axes.labelcolor": "#24292f",
        "text.color": "#24292f",
        "xtick.color": "#57606a",
        "ytick.color": "#57606a",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    })
    BLUE, GREEN, AMBER, RED, GRAY = "#1f6feb", "#2ea043", "#d29922", "#da3633", "#6e7781"
    files: list[str] = []

    def finish(fig, name: str) -> None:
        fig.tight_layout()
        path = out / name
        fig.savefig(path, dpi=170, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        files.append(str(path))

    def clean(ax, grid_axis: str = "y") -> None:
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.grid(axis=grid_axis, alpha=0.25, linewidth=0.8)
        ax.set_axisbelow(True)

    # 1. pipeline status -----------------------------------------------------
    by_status = m["inventory"]["by_status"]
    order = ["NEW", "NORMALIZED", "ENRICHED", "SCORED", "MONITORED", "PUBLISHED",
             "REJECTED", "EXPIRED", "REMOVED"]
    labels = [s for s in order if s in by_status]
    values = [by_status[s] for s in labels]
    colors = [GRAY if s in ("NEW", "NORMALIZED", "ENRICHED", "SCORED") else
              GREEN if s in ("MONITORED", "PUBLISHED") else
              AMBER if s == "EXPIRED" else RED for s in labels]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    bars = ax.bar(labels, values, color=colors, width=0.62)
    for b, v in zip(bars, values):
        ax.text(b.get_x() + b.get_width() / 2, v + max(values) * 0.015, str(v),
                ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_title("Repartition des indicateurs par etape du cycle de vie")
    ax.set_ylabel("Nombre d'indicateurs")
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    clean(ax)
    finish(fig, "eval_01_cycle_de_vie.png")

    # 2. score distribution --------------------------------------------------
    dist = m["scoring"]["distribution"]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    names = list(dist.keys())
    vals = list(dist.values())
    colors = [RED, AMBER, AMBER, GREEN, GREEN]
    bars = ax.bar(names, vals, color=colors, width=0.6)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + max(vals or [1]) * 0.02, str(v),
                ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_title("Distribution des scores et seuils de decision")
    ax.set_ylabel("Nombre d'indicateurs")
    ax.set_xlabel("Score / 100  (seuils : <50 rejet, 50-79 surveillance, >=80 publication)")
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    plt.setp(ax.get_xticklabels(), rotation=18, ha="right")
    clean(ax)
    finish(fig, "eval_02_scores.png")

    # 3. funnel --------------------------------------------------------------
    f = m["lifecycle"]["by_target_status"]
    staged = [("Normalises", f.get("NORMALIZED", 0)),
              ("Enrichis", f.get("ENRICHED", 0)),
              ("Notes", f.get("SCORED", 0)),
              ("Surveilles", f.get("MONITORED", 0)),
              ("Publies", f.get("PUBLISHED", 0)),
              ("Expires", f.get("EXPIRED", 0)),
              ("Retires", f.get("REMOVED", 0))]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    xs = [x for x, _ in staged]
    ys = [y for _, y in staged]
    bars = ax.barh(xs[::-1], ys[::-1], color=[BLUE, BLUE, BLUE, GREEN, GREEN, AMBER, RED][::-1], height=0.6)
    for b, v in zip(bars, ys[::-1]):
        ax.text(v + max(ys or [1]) * 0.015, b.get_y() + b.get_height() / 2, str(v),
                va="center", fontsize=9, fontweight="bold")
    ax.set_title("Entonnoir du cycle de vie (transitions observees)")
    ax.set_xlabel("Nombre de transitions")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    clean(ax, "x")
    finish(fig, "eval_03_entonnoir.png")

    # 4. enrichment verdicts -------------------------------------------------
    by_verdict = m["enrichment"]["by_verdict"]
    providers = sorted({k.split("/")[0] for k in by_verdict})
    verdicts = ["malicious", "suspicious", "benign", "unknown"]
    vcolors = {"malicious": RED, "suspicious": AMBER, "benign": GREEN, "unknown": GRAY}
    fig, ax = plt.subplots(figsize=(7.5, 4))
    bottom = [0] * len(providers)
    for verdict in verdicts:
        vals = [by_verdict.get(f"{p}/{verdict}", 0) for p in providers]
        ax.bar(providers, vals, bottom=bottom, label=verdict, color=vcolors[verdict], width=0.5)
        bottom = [b + v for b, v in zip(bottom, vals)]
    for i, total in enumerate(bottom):
        ax.text(i, total + max(bottom or [1]) * 0.02, str(total), ha="center", fontsize=9, fontweight="bold")
    ax.set_title("Verdicts d'enrichissement par fournisseur")
    ax.set_ylabel("Resultats d'enrichissement")
    ax.legend(frameon=False, ncol=4, fontsize=8.5, loc="upper center", bbox_to_anchor=(0.5, -0.1))
    clean(ax)
    finish(fig, "eval_04_enrichissement.png")

    # 5. collection / dedup --------------------------------------------------
    d = m["dedup"]
    fig, ax = plt.subplots(figsize=(8, 4))
    names = ["Collectes", "Creations", "Mises a jour", "Doublons ecartes", "Invalides rejetes"]
    vals = [d["raw_items_collected"], d["created"], d["updated"],
            d["duplicates_dropped_at_ingest"], d["invalid_rejected"]]
    bars = ax.bar(names, vals, color=[BLUE, GREEN, BLUE, AMBER, RED], width=0.6)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + max(vals or [1]) * 0.02, str(v),
                ha="center", fontsize=9, fontweight="bold")
    ax.set_title(f"Volume collecte et qualite (taux de dedup : {d['dedup_rate_pct']} %)")
    ax.set_ylabel("Elements")
    plt.setp(ax.get_xticklabels(), rotation=15, ha="right")
    clean(ax)
    finish(fig, "eval_05_collecte_dedup.png")

    # 6. automation comparison ----------------------------------------------
    a = m["automation"]
    manual = a["manual_minutes_per_ioc"]
    auto = a["automated_minutes_per_ioc"] or 0
    fig, ax = plt.subplots(figsize=(7.5, 4))
    bars = ax.bar(["Modele manuel\n(hypothese)", "Plateforme\n(mesure)"], [manual, auto],
                  color=[GRAY, GREEN], width=0.45)
    for b, v in zip(bars, [manual, auto]):
        ax.text(b.get_x() + b.get_width() / 2, v + max(manual, auto) * 0.03,
                f"{v:g} min", ha="center", fontsize=10, fontweight="bold")
    ax.set_title(f"Temps de traitement par indicateur (x{a['time_reduction_factor']})")
    ax.set_ylabel("Minutes par indicateur")
    ax.set_ylim(0, manual * 1.25)
    clean(ax)
    finish(fig, "eval_06_automatisation.png")

    # 7. sources -------------------------------------------------------------
    src = [s for s in m["sources"] if s["ioc_count"] > 0]
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    names = [s["name"] for s in src]
    vals = [s["ioc_count"] for s in src]
    bars = ax.barh(names[::-1], vals[::-1], color=BLUE, height=0.55)
    for b, v in zip(bars, vals[::-1]):
        ax.text(v + max(vals or [1]) * 0.02, b.get_y() + b.get_height() / 2, str(v),
                va="center", fontsize=9, fontweight="bold")
    ax.set_title("Contribution des sources (indicateurs distincts)")
    ax.set_xlabel("Nombre d'indicateurs")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    clean(ax, "x")
    finish(fig, "eval_07_sources.png")

    return files


# -------------------------------------------------------------------- docs --
def render_markdown(m: dict[str, Any], figures: list[str]) -> str:
    inv, ded, enr, sco = m["inventory"], m["dedup"], m["enrichment"], m["scoring"]
    pub, det, lif, perf = m["publication"], m["detection"], m["lifecycle"], m["performance"]
    aud, aut = m["audit"], m["automation"]

    def table(headers: list[str], rows: list[list[Any]]) -> str:
        out = ["| " + " | ".join(headers) + " |",
               "|" + "|".join(["---"] * len(headers)) + "|"]
        for row in rows:
            out.append("| " + " | ".join(str(c) for c in row) + " |")
        return "\n".join(out)

    lines: list[str] = []
    add = lines.append

    add("# Phase 7 - Evaluation de l'usine a indicateurs\n")
    add(f"> Genere automatiquement le {m['generated_at']} depuis la base "
        f"`{m['database']}` - **aucune valeur n'est inventee**.\n")
    add("Ce document distingue systematiquement :\n")
    add("- les **mesures** : lues dans PostgreSQL (inventaire, scores, detections, audit) ;\n"
        "- les **hypotheses** : le modele manuel de comparaison, explicitement pose et "
        "modifiable dans `scripts/evaluate_platform.py` ;\n"
        "- ce qui **n'a pas pu etre mesure**, avec la raison.\n")

    add("## 1. Inventaire traite\n")
    add(table(["Indicateur", "Valeur"], [
        ["Indicateurs en base", inv["total_iocs"]],
        ["Types", ", ".join(f"{k}={v}" for k, v in sorted(inv["by_type"].items(), key=lambda x: -x[1]))],
        ["Niveaux de risque", ", ".join(f"{k}={v}" for k, v in inv["by_risk"].items()) or "aucun"],
        ["Synthetiques (marques `is_synthetic`)", inv["synthetic_iocs"]],
        ["Avec empreinte de doublon", inv["with_duplicate_of"]],
        ["Avec date d'expiration", inv["with_expiry"]],
    ]))
    add("")

    add("## 2. Qualite de la donnee et deduplication\n")
    add(table(["Mesure", "Valeur"], [
        ["Elements bruts collectes", ded["raw_items_collected"]],
        ["Indicateurs crees", ded["created"]],
        ["Indicateurs mis a jour", ded["updated"]],
        ["Doublons ecartes a l'ingestion", ded["duplicates_dropped_at_ingest"]],
        ["Valeurs invalides rejetees", ded["invalid_rejected"]],
        ["**Taux de deduplication** (DEDUP / NORMALIZE+DEDUP)", f"**{ded['dedup_rate_pct']} %**"],
        ["Part de l'inventaire issu d'un doublon", f"{ded['duplicate_rate_of_inventory_pct']} %"],
    ]))
    add("")
    add("> Le taux de deduplication est calcule sur les evenements d'audit "
        "(`DEDUP` / (`NORMALIZE` + `DEDUP`)), pas sur une estimation.\n")

    add("## 3. Enrichissement\n")
    add(table(["Mesure", "Valeur"], [
        ["Resultats d'enrichissement stockes", enr["results"]],
        ["Indicateurs enrichis", enr["iocs_enriched"]],
        ["Couverture", f"{enr['coverage_pct']} %"],
        ["Taux de succes fournisseurs", f"{enr['provider_success_pct']} %"],
        ["Erreurs fournisseurs", enr["provider_errors"]],
        ["Resultats moyens par indicateur enrichi", enr["avg_results_per_enriched_ioc"]],
        ["Repartition par fournisseur", ", ".join(f"{k}={v}" for k, v in enr["by_provider"].items())],
        ["Repartition par verdict", ", ".join(f"{k}={v}" for k, v in sorted(enr["by_verdict"].items()))],
    ]))
    add("")

    add("## 4. Notation et decisions\n")
    add(table(["Mesure", "Valeur"], [
        ["Indicateurs notes", f"{sco['scored_iocs']} ({sco['coverage_pct']} %)"],
        ["Score moyen", sco["avg"]],
        ["Score median", sco["median"]],
        ["95e percentile", sco["p95"]],
        ["Minimum / maximum", f"{sco['min']} / {sco['max']}"],
        ["Notation explicable (score_breakdown)", f"{sco['explainable_iocs']} ({sco['explainability_pct']} %)"],
        ["Politique active", sco["policy"]],
    ]))
    add("")
    add(table(["Decision", "Indicateurs", "Part des indicateurs notes"], [
        [k, v, f"{sco['decisions_pct'][k]} %"] for k, v in sco["decisions"].items()
    ]))
    add("")
    add("### Contribution moyenne des composantes du score\n")
    add(table(["Composante", "Points moyens", "Maximum", "% du maximum"], [
        [c["label"], c["avg_points"], c["max_points"], c["avg_pct_of_max"]]
        for c in sco["components_avg"]
    ]))
    add("")
    add("> Un score sans detection reste plafonne autour de 67/100 : c'est la "
        "composante `observed_detections` (15 points) qui permet d'atteindre le seuil "
        "de publication (>= 80). Les indicateurs publies le sont donc **parce qu'un "
        "capteur les a reellement observes**, pas par empilement de sources.\n")

    add("## 5. Publication et verification\n")
    add(table(["Mesure", "Valeur"], [
        ["Publications enregistrees", pub["total"]],
        ["Verifiees par relecture", pub["verified"]],
        ["Retirees (revocation confirmee)", pub["revoked"]],
        ["Actives", pub["active"]],
        ["Indicateurs au statut PUBLISHED", pub["published_iocs"]],
    ]))
    add("")

    add("## 6. Detections\n")
    add(table(["Mesure", "Valeur"], [
        ["Detections enregistrees", det["total"]],
        ["Indicateurs ayant declenche", det["iocs_with_detections"]],
        ["Couverture de l'inventaire", f"{det['coverage_pct']} %"],
        ["Faux positifs", det["false_positives"]],
        ["Taux de faux positifs", f"{det['false_positive_rate_pct']} %"],
        ["Par capteur", ", ".join(f"{k}={v}" for k, v in det["by_sensor"].items())],
    ]))
    add("")

    add("## 7. Cycle de vie et delais\n")
    add(table(["Etape (transition)", "Observee", "Duree moyenne (a chaud)", "Duree max"], [
        [s["stage"], s["observed"],
         f"{s['avg_seconds_hot']} s" if s["avg_seconds_hot"] is not None else "n/a",
         f"{s['max_seconds']} s"]
        for s in lif["stages"]
    ]))
    add("")
    if lif["full_cycles"]:
        cyc = lif["full_cycles"][0]
        add(f"- Cycle complet mesure (NEW -> REMOVED) : **{cyc['seconds']} s** "
            f"({round(cyc['seconds']/60, 1)} min), {cyc['transitions']} transitions tracees, "
            f"indicateur `{cyc['value']}`.")
    add(f"- Transitions journalisees au total : **{lif['transitions_total']}**.")
    add("")
    add("> Les durees Â« a chaud Â» excluent le backlog repris apres un arret volontaire "
        "de la plateforme ; les durees completes restent visibles dans `metrics.json`.\n")

    add("## 8. Performance mesuree\n")
    add(table(["Mesure", "Valeur"], [
        ["Traitement a chaud (ingestion -> score)", f"{perf['hot_latency_avg_s']} s en moyenne "
                                                     f"sur {perf['hot_latency_iocs']} indicateurs"],
        ["Debit du lot a chaud", f"{perf.get('hot_batch_throughput_ioc_per_s')} indicateurs/s"],
        ["Backlog repris apres arret", f"{perf['backlog_iocs']} indicateurs, "
                                       f"{perf['backlog_latency_avg_h']} h en moyenne"],
        ["Moteur de notation (CPU pur)", f"{perf['scoring_engine'].get('us_per_score')} us/score "
                                         f"= {perf['scoring_engine'].get('scores_per_second')} scores/s"],
    ]))
    add("")
    if perf.get("backlog_note"):
        add(f"> {perf['backlog_note']}\n")

    add("## 9. Automatisation : avant / apres\n")
    add("**Apres (mesure)** : la plateforme a traite l'inventaire ci-dessus avec les "
        f"latences reelles du tableau precedent.\n")
    add("**Avant (hypothese documentee)** : modele d'un analyste sans automatisation, "
        "temps unitaires par indicateur :\n")
    add(table(["Etape manuelle", "Minutes / indicateur"], [
        [k.replace("_", " "), v] for k, v in aut["manual_baseline"]["unit_minutes_per_ioc"].items()
    ]))
    add("")
    add(table(["Comparaison", "Valeur"], [
        ["Total manuel par indicateur (hypothese)", f"{aut['manual_minutes_per_ioc']} min"],
        ["Total automatise par indicateur (mesure)", f"{aut['automated_minutes_per_ioc']} min"],
        ["Facteur de reduction", f"x{aut['time_reduction_factor']}"],
        ["Charge manuelle pour cet inventaire (hypothese)", f"{aut['manual_hours_for_inventory']} h"],
        ["Charge automatisee pour cet inventaire", f"{aut['automated_hours_for_inventory']} h"],
        ["Temps economise (hypothese)", f"{aut['hours_saved_for_inventory']} h"],
    ]))
    add("")
    add(f"> {aut['manual_baseline']['note']}\n")

    add("## 10. TraÃ§abilite\n")
    add(table(["Action d'audit", "Evenements"], [[k, v] for k, v in aud["by_action"].items()]))
    add("")
    add(f"- Total : **{aud['events']}** evenements, dont **{aud['failed']}** en echec "
        "(les echecs sont conserves, jamais masques).")
    add("- Le journal est **append-only** : un trigger PostgreSQL refuse tout UPDATE et DELETE "
        "(verifie par test automatise).\n")

    add("## 11. Sources\n")
    add(table(["Source", "Type", "Fiabilite", "Active", "Indicateurs"], [
        [s["name"], s["kind"], s["reliability"], "oui" if s["enabled"] else "non", s["ioc_count"]]
        for s in m["sources"]
    ]))
    add("")

    if figures:
        add("## 12. Figures\n")
        for path in figures:
            name = Path(path).name
            add(f"![{name}]({Path(path).as_posix()})\n")

    add("## 13. Limites assumees\n")
    add("- Les **faux positifs** ne sont renseignes que pour les detections revues ; "
        "les detections non revues restent `NULL` et ne sont pas comptees comme benignes.")
    add("- Le **modele manuel** est une hypothese de comparaison, pas une mesure historique.")
    add("- Les collecteurs URLhaus / ThreatFox / MalwareBazaar sont **inactifs** : la cle "
        "abuse.ch fournie a ete refusee par le serveur (`unknown_auth_key`). Aucune donnee "
        "n'a ete simulee pour compenser.")
    add("- Le **backlog** (indicateurs traites apres l'arret de la plateforme) gonfle la "
        "latence moyenne globale ; il est isole dans les metriques.")
    add("- La **precision/rappel** au sens strict exigerait un jeu de verite terrain annote ; "
        "les indicateurs etant issus de flux publics, aucune verite terrain n'est revendiquee. "
        "Les proxies reportes (taux de publication, taux de faux positifs observes, couverture "
        "d'enrichissement) sont ceux qui sont reellement mesurables ici.\n")

    return "\n".join(lines) + "\n"


# -------------------------------------------------------------------- main --
def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--figures", type=Path, default=DEFAULT_FIGS)
    parser.add_argument("--no-charts", action="store_true")
    args = parser.parse_args()

    engine = db_engine()
    try:
        metrics = collect_metrics(engine)
    finally:
        engine.dispose()

    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(metrics, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    figures: list[str] = []
    if not args.no_charts:
        try:
            figures = make_charts(metrics, args.figures)
        except Exception as exc:
            metrics["notes"].append(f"figures non generees: {type(exc).__name__}: {exc}")
            args.json.write_text(json.dumps(metrics, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    args.md.write_text(render_markdown(metrics, figures), encoding="utf-8")

    inv, sco = metrics["inventory"], metrics["scoring"]
    print(f"metrics   : {args.json}")
    print(f"rapport   : {args.md}")
    print(f"figures   : {len(figures)} -> {args.figures}")
    print(f"inventaire: {inv['total_iocs']} IOC | notes {sco['scored_iocs']} | "
          f"score moyen {sco['avg']} | dedup {metrics['dedup']['dedup_rate_pct']} %")
    print(f"latence a chaud: {metrics['performance']['hot_latency_avg_s']} s "
          f"| facteur d'automatisation x{metrics['automation']['time_reduction_factor']} (hypothese)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

