"""Register the real intelligence sources in the database (idempotent)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models.ioc import IntelSource, SourceKind  # noqa: E402

SOURCES = [
    # (name, provenance_group, reliability, url, kind, requires_key, rpm)
    ("feodotracker", "abuse_ch", 75,
     "https://feodotracker.abuse.ch/downloads/ipblocklist.txt",
     SourceKind.COMMUNITY, False, 12),
    ("blocklist_de", "blocklist_de", 60,
     "https://lists.blocklist.de/lists/all.txt",
     SourceKind.COMMUNITY, False, 12),
    ("urlscan", "urlscan", 70,
     "https://urlscan.io/api/v1/search/",
     SourceKind.OPEN_SOURCE, False, 30),
    ("alienvault_otx", "alienvault", 80,
     "https://otx.alienvault.com/api/v1/",
     SourceKind.OPEN_SOURCE, False, 60),
    # abuse.ch feeds: collected only when ABUSECH_AUTH_KEY is configured.
    ("urlhaus", "abuse_ch", 70,
     "https://urlhaus-api.abuse.ch/v1/",
     SourceKind.COMMUNITY, True, 10),
    ("threatfox", "abuse_ch", 75,
     "https://threatfox-api.abuse.ch/api/v1/",
     SourceKind.COMMUNITY, True, 10),
    ("malwarebazaar", "abuse_ch", 70,
     "https://mb-api.abuse.ch/api/v1/",
     SourceKind.COMMUNITY, True, 10),
    ("synthetic_lab", "synthetic_lab", 50,
     None, SourceKind.SYNTHETIC, False, 1000),
]


def main() -> int:
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    pwd = os.environ["POSTGRES_PASSWORD"]
    engine = create_engine(
        f"postgresql+psycopg://soar:{pwd}@{host}:5432/soar_ioc", future=True
    )
    created = updated = 0
    with Session(engine) as db:
        for name, group, rel, url, kind, key, rpm in SOURCES:
            src = db.execute(
                select(IntelSource).where(IntelSource.name == name)
            ).scalar_one_or_none()
            if src is None:
                db.add(IntelSource(
                    name=name, provenance_group=group, reliability=rel,
                    url=url, kind=kind, requires_api_key=key,
                    rate_limit_rpm=rpm, enabled=True,
                ))
                created += 1
            else:
                src.reliability = rel
                src.requires_api_key = key
                src.rate_limit_rpm = rpm
                updated += 1
        db.commit()

        print(f"sources: {created} creees, {updated} mises a jour")
        for s in db.execute(select(IntelSource).order_by(IntelSource.name)).scalars():
            flag = "CLE REQUISE (desactive pour la collecte)" if s.requires_api_key else "sans cle"
            print(f"  - {s.name:16} groupe={s.provenance_group:15} "
                  f"fiab={s.reliability:3} {flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
