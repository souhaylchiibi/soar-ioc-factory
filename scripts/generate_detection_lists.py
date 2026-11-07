"""Generate detection lists from PUBLISHED indicators.

Outputs:
* integrations/suricata/rules/soar-ioc.rules  — Suricata rules (one per IOC)
* integrations/wazuh/lists/soar-ioc.txt       — flat list for Wazuh/decoders
* integrations/misp/detection-list.csv        — portable list (MISP import)

Only PUBLISHED indicators are distributed to detection systems; MONITORED
ones stay internal. Re-running is idempotent (same file content).
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, select

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.models.ioc import Ioc, IocStatus, IocType  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SURICATA_RULES = ROOT / "integrations" / "suricata" / "rules" / "soar-ioc.rules"
WAZUH_LIST = ROOT / "integrations" / "wazuh" / "lists" / "soar-ioc.txt"
MISP_CSV = ROOT / "integrations" / "misp" / "detection-list.csv"


def _esc(value: str) -> str:
    """Escape a value for use inside a Suricata rule (no quotes/semicolons)."""
    return value.replace('"', "").replace(";", "").replace("'", "")


def suricata_rule(ioc: Ioc) -> str | None:
    """One Suricata rule per indicator type. IDS-only alerting (no drop)."""
    sid_base = 900000  # labo range, unambiguous ownership
    if ioc.type == IocType.IP:
        return (
            f'alert ip $HOME_NET any -> {_esc(ioc.value)} any '
            f'(msg:"SOAR-IOC tracked IP { _esc(ioc.value) }"; sid:{sid_base + int(ioc.id.int % 90000)}; rev:1; '
            f'classtype:targeted-activity;)'
        )
    if ioc.type in (IocType.DOMAIN, IocType.URL):
        host = _esc(ioc.value)
        # DNS query containing the tracked hostname (QNAME = len+label ... 0x00).
        escaped_host = host.replace(".", r"\.")
        pcre = r"/\x01[\x00-\xff]{7}\x01" + escaped_host + r"\x00/"
        return (
            f'alert dns any any -> any any (msg:"SOAR-IOC tracked domain {host}"; '
            f'content:"|01 00 00 01|"; offset:2; depth:4; '
            f'pcre:"{pcre}"; '
            f'sid:{sid_base + int(ioc.id.int % 90000)}; rev:1; classtype:targeted-activity;)'
        )
    if ioc.type in (IocType.HASH_MD5, IocType.HASH_SHA1, IocType.HASH_SHA256):
        # File hashes are matched by filestore/HTTP downloads — expressed as a
        # content match on the hex string (works for URLs exposing the hash).
        return (
            f'alert http any any -> any any (msg:"SOAR-IOC tracked hash {_esc(ioc.value)}"; '
            f'content:"{_esc(ioc.value)}"; nocase; '
            f'sid:{sid_base + int(ioc.id.int % 90000)}; rev:1; classtype:targeted-activity;)'
        )
    return None


def main() -> int:
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    pwd = os.environ["POSTGRES_PASSWORD"]
    engine = create_engine(
        f"postgresql+psycopg://soar:{pwd}@{host}:5432/soar_ioc", future=True
    )

    from sqlalchemy.orm import Session as OrmSession

    with OrmSession(engine) as db:
        published = db.execute(
            select(Ioc).where(Ioc.status == IocStatus.PUBLISHED)
        ).scalars().all()

    if not published:
        print("aucun IOC PUBLISHED : listes non generées (aucune donnee fabriquee)")
        return 3

    # --- Suricata rules --------------------------------------------------
    rules: list[str] = [
        "# Genere par scripts/generate_detection_lists.py — NE PAS EDITER A LA MAIN",
        "# Source: IOC au statut PUBLISHED uniquement",
        "# Mode IDS (alert) — aucun blocage (aucune action inline/DROP en labo)",
    ]
    sids: set[int] = set()
    for ioc in published:
        rule = suricata_rule(ioc)
        if rule is None:
            continue
        sid = int(rule.split("sid:")[1].split(";")[0])
        if sid in sids:            # collision: derive a new sid deterministically
            sid = sid + 1
            rule = rule.replace(f"sid:{int(rule.split('sid:')[1].split(';')[0])};", f"sid:{sid};")
        sids.add(sid)
        rules.append(rule)

    SURICATA_RULES.parent.mkdir(parents=True, exist_ok=True)
    SURICATA_RULES.write_text("\n".join(rules) + "\n", encoding="utf-8")

    # --- Wazuh flat list --------------------------------------------------
    WAZUH_LIST.parent.mkdir(parents=True, exist_ok=True)
    WAZUH_LIST.write_text(
        "# SOAR IOC detection list (PUBLISHED only)\n"
        + "\n".join(i.value for i in published) + "\n",
        encoding="utf-8",
    )

    # --- Portable CSV (MISP import) ---------------------------------------
    MISP_CSV.parent.mkdir(parents=True, exist_ok=True)
    with MISP_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["type", "value", "score", "risk_level", "first_seen", "expires_at", "ioc_id"])
        for i in published:
            w.writerow([i.type.value, i.value, i.score, i.risk_level.value if i.risk_level else "",
                        i.first_seen_at.isoformat() if i.first_seen_at else "",
                        i.expires_at.isoformat() if i.expires_at else "", str(i.id)])

    print(f"IOC PUBLISHED : {len(published)}")
    print(f"  -> {SURICATA_RULES.relative_to(ROOT)}  ({len(rules) - 3} regles)")
    print(f"  -> {WAZUH_LIST.relative_to(ROOT)}")
    print(f"  -> {MISP_CSV.relative_to(ROOT)}")
    for i in published:
        print(f"     {i.type.value:10} {i.value[:48]:48} score={i.score}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
