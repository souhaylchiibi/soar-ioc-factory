"""Collect the measured facts used by the project report and the deck (reports/data/facts.json).

Sources (nothing is typed by hand except the test/scan results, which are
recorded with the command that produced them on 16/11/2026):
  * local PostgreSQL, through the application's own query functions;
  * the AWS deployment, through `psql` over SSH (optional: --aws-json FILE);
  * git for repository statistics.

Usage (from the repo root, DB env vars set as for the tests):
  backend/.venv/Scripts/python.exe scripts/collect_facts.py [--aws-json reports/data/aws.json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.api.iocs import dashboard_stats  # noqa: E402
from app.api.soc import lifecycle_funnel, sources_overview, timeline, workflow_runs  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.models.ioc import AuditLog  # noqa: E402
from sqlalchemy import select  # noqa: E402

OUT = ROOT / "reports" / "data" / "facts.json"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aws-json", type=Path, help="JSON produced on the EC2 host")
    args = parser.parse_args()

    with SessionLocal() as db:
        stats = dashboard_stats(db).model_dump()
        funnel = lifecycle_funnel(db)
        series = timeline(db, days=30)
        sources = sources_overview(db)
        runs = workflow_runs(db, action=None, actor=None, offset=0, limit=200)
        # Machine time actually spent per pipeline stage (runs that recorded duration_ms).
        processing: dict[str, dict] = {}
        for a in db.execute(select(AuditLog).where(AuditLog.entity_type == "batch")).scalars():
            d = a.detail if isinstance(a.detail, dict) else {}
            if not isinstance(d.get("duration_ms"), (int, float)):
                continue
            items = next((d[k] for k in ("created", "enriched", "scored", "published", "expired", "removed", "matched", "normalized")
                          if isinstance(d.get(k), int)), 0)
            if a.action == "COLLECT":
                items = sum(d.get(k, 0) for k in ("created", "updated", "duplicates", "rejected"))
            if a.action == "ENRICH":
                items = d.get("targets", items)
            st = processing.setdefault(a.action, {"runs": 0, "duration_ms": 0, "items": 0})
            st["runs"] += 1
            st["duration_ms"] += int(d["duration_ms"])
            st["items"] += int(items or 0)

    facts = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "local": {
            "stats": stats,
            "funnel": funnel,
            "timeline": series["series"],
            "sources": sources["sources"],
            "runs": {"total": runs["total"], "failed": runs["failed_total"],
                     "measured": sum(1 for r in runs["runs"] if r["duration_ms"] is not None)},
            "processing": processing,
        },
        "aws": json.loads(args.aws_json.read_text(encoding="utf-8")) if args.aws_json else None,
        "repo": {
            "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "commit": git("rev-parse", "--short", "HEAD"),
            "commits": int(git("rev-list", "--count", "HEAD") or 0),
            "tracked_files": len(git("ls-files").splitlines()),
        },
        # Results of the commands run on 16/11/2026 (see docs/TESTING.md).
        "tests": [
            {"suite": "API et moteur (PostgreSQL réel)", "tool": "pytest", "count": 224, "passed": 224,
             "command": "pytest tests -q"},
            {"suite": "Console — composants et pages", "tool": "Vitest + RTL", "count": 23, "passed": 23,
             "command": "npm test"},
            {"suite": "Bout en bout — poste local", "tool": "Playwright", "count": 8, "passed": 8,
             "command": "npm run test:e2e"},
            {"suite": "Bout en bout — serveur AWS (tunnel)", "tool": "Playwright", "count": 8, "passed": 8,
             "command": "E2E_BASE_URL=http://127.0.0.1:8091 npm run test:e2e"},
        ],
        "security_scans": [
            {"tool": "Bandit", "scope": "code Python de l'API", "result": "aucun problème"},
            {"tool": "pip-audit", "scope": "dépendances Python", "result": "aucune vulnérabilité connue"},
            {"tool": "npm audit", "scope": "dépendances JavaScript", "result": "aucune vulnérabilité"},
            {"tool": "Trivy", "scope": "image API, Dockerfiles, compose", "result": "0 HIGH/CRITICAL corrigeable, aucun secret"},
            {"tool": "OWASP ZAP", "scope": "console + API", "result": "0 échec, 60 contrôles réussis, 2 avertissements documentés"},
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(facts, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"facts -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
