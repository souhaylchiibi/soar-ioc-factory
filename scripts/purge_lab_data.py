"""Purge lab data (TRUNCATE) — user-approved reset of this session's demo data.

TRUNCATE is a table-level operation and does NOT fire the row-level
append-only trigger; the audit trail protection stays intact for
UPDATE/DELETE of individual rows.
"""
import os
import sys

from sqlalchemy import create_engine, text

TABLES = (
    "detections, publications, score_history, enrichments, lifecycle_events, "
    "ioc_sources, iocs, intel_sources, users, reports, scoring_policies, audit_logs"
)


def main() -> int:
    if os.environ.get("CONFIRM_PURGE") != "YES-I-APPROVE":
        print("REFUSE: set CONFIRM_PURGE=YES-I-APPROVE to run this reset")
        return 2

    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    pwd = os.environ["POSTGRES_PASSWORD"]
    engine = create_engine(
        f"postgresql+psycopg://soar:{pwd}@{host}:5432/soar_ioc",
        future=True, isolation_level="AUTOCOMMIT",
    )
    with engine.connect() as conn:
        before = conn.execute(text("SELECT count(*) FROM iocs")).scalar()
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
        after = conn.execute(text("SELECT count(*) FROM iocs")).scalar()
        # Verify the append-only trigger survived the purge.
        trig = conn.execute(text(
            "SELECT tgname FROM pg_trigger WHERE tgname='trg_audit_immutable'"
        )).scalar()
    engine.dispose()
    print(f"purge: iocs {before} -> {after}")
    print(f"trigger append-only toujours actif: {'OUI' if trig else 'NON !!'}")
    return 0 if after == 0 and trig else 1


if __name__ == "__main__":
    sys.exit(main())
