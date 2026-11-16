"""Collect the measured facts used by the v0.2 report (reports/v2/facts.json).

Sources (nothing is typed by hand except the test/scan results, which are
recorded with the command that produced them on 16/11/2026):
  * local PostgreSQL, through the application's own query functions;
  * the AWS deployment, through `psql` over SSH (optional: --aws-json FILE);
  * git for repository statistics.

Usage (from the repo root, DB env vars set as for the tests):
  backend/.venv/Scripts/python.exe scripts/collect_v2_facts.py [--aws-json aws.json]
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

OUT = ROOT / "reports" / "v2" / "facts.json"


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

    facts = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "local": {
            "stats": stats,
            "funnel": funnel,
            "timeline": series["series"],
            "sources": sources["sources"],
            "runs": {"total": runs["total"], "failed": runs["failed_total"],
                     "measured": sum(1 for r in runs["runs"] if r["duration_ms"] is not None)},
        },
        "aws": json.loads(args.aws_json.read_text(encoding="utf-8")) if args.aws_json else None,
        "repo": {
            "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "commit": git("rev-parse", "--short", "HEAD"),
            "commits": int(git("rev-list", "--count", "HEAD") or 0),
            "tracked_files": len(git("ls-files").splitlines()),
            "v02_diff": git("diff", "--shortstat", "HEAD~1", "HEAD"),
        },
        # Results of the commands run on 16/11/2026 (see docs/LIVRAISON_V2.md §5).
        "tests": [
            {"suite": "Backend pytest (PostgreSQL réel)", "tool": "pytest", "count": 224, "passed": 224,
             "command": "pytest tests -q"},
            {"suite": "Frontend unitaires", "tool": "Vitest + RTL", "count": 23, "passed": 23,
             "command": "npm test"},
            {"suite": "End-to-end local", "tool": "Playwright", "count": 8, "passed": 8,
             "command": "npm run test:e2e"},
            {"suite": "End-to-end AWS (tunnel)", "tool": "Playwright", "count": 8, "passed": 8,
             "command": "E2E_BASE_URL=http://127.0.0.1:8091 npm run test:e2e"},
        ],
        "security_scans": [
            {"tool": "Bandit", "before": 1, "after": 0, "note": "1 faux positif B105 annoté"},
            {"tool": "pip-audit", "before": 24, "after": 0, "note": "Starlette 0.41.3 (7) + PyJWT 2.10.1 (17)"},
            {"tool": "npm audit", "before": 3, "after": 0, "note": "outillage Vitest 3 (dev)"},
            {"tool": "Trivy image", "before": 3, "after": 0, "note": "zlib1g, wheel, jaraco.context (HIGH)"},
            {"tool": "Trivy config", "before": 1, "after": 0, "note": "nginx exécuté en root (DS-0002)"},
            {"tool": "OWASP ZAP", "before": 0, "after": 0, "note": "0 FAIL, 60 PASS, 2 WARN documentés"},
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(facts, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"facts -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
