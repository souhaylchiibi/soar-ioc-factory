"""
Démo Phase 3 — cycle complet via l'API REST (données SYNTHÉTIQUES de labo).

Exécute : enregistrement des sources -> ingest -> scoring -> décisions -> stats.
Affiche chaque étape. Ne contient AUCUNE donnée IOC réelle.
"""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"


def call(method: str, path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        print(f"  !! HTTP {exc.code} {method} {path}: {body[:300]}")
        return {"_error": exc.code, "_body": body}


def main() -> int:
    # ---- 1. Enregistrer les sources (provenance anti-collusion) --------
    print("=" * 70)
    print("ETAPE 1 — Sources de renseignement (groupe de provenance)")
    print("=" * 70)
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    import os

    # Connexion directe base pour enregistrer les sources (setup only).
    host = os.environ["POSTGRES_HOST"]
    pwd = os.environ["POSTGRES_PASSWORD"]
    engine = create_engine(
        f"postgresql+psycopg://soar:{pwd}@{host}:5432/soar_ioc", future=True
    )
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from app.models.ioc import IntelSource, SourceKind  # noqa: E402

    with Session(engine) as db:
        known = {s.name for s in db.execute(select(IntelSource)).scalars()}
        for name, group, rel in [
            ("synthetic_lab", "synthetic_lab", 60),
            ("echo_feed_lab", "synthetic_lab", 60),   # meme groupe = 1 source
            ("indep_org_lab", "indep_org_lab", 90),
        ]:
            if name not in known:
                db.add(IntelSource(name=name, provenance_group=group,
                                   reliability=rel, kind=SourceKind.SYNTHETIC))
        db.commit()
        for s in db.execute(select(IntelSource)).scalars():
            print(f"  - {s.name:18} groupe={s.provenance_group:15} fiabilite={s.reliability}")

    # ---- 2. Ingestion du corpus synthétique ---------------------------
    print("\n" + "=" * 70)
    print("ETAPE 2 — Ingestion (normalisation + dedup + rejets)")
    print("=" * 70)

    from app.collectors.synthetic import SyntheticCollector  # noqa: E402

    items = []
    for raw in SyntheticCollector().collect():
        items.append({
            "value": raw.value,
            "type": raw.context.get("declared_type"),
            "source": raw.source_name,
            "first_seen_at": raw.first_seen_at.isoformat() if raw.first_seen_at else None,
            "last_seen_at": raw.last_seen_at.isoformat() if raw.last_seen_at else None,
            "expires_at": raw.context.get("expires_at").isoformat()
                if raw.context.get("expires_at") else None,
            "tags": raw.tags,
            "external_id": raw.external_id,
            "is_synthetic": True,
        })

    resp = call("POST", "/iocs/ingest", {"items": items})
    if "_error" in resp:
        return 1
    print(f"  crees={resp['created']}  mises_a_jour={resp['updated']}  "
          f"doublons={resp['duplicates']}  rejetees={resp['rejected']}")
    for r in resp["results"]:
        mark = {"created": "+", "updated": "=", "duplicate": "D",
                "rejected": "X"}[r["action"]]
        reason = f"  ({r['reason'][:70]})" if r["action"] == "rejected" else ""
        print(f"   [{mark}] {r['action']:9} {r['raw_value'][:55]}{reason}")

    # ---- 3. Scoring + decisions ---------------------------------------
    print("\n" + "=" * 70)
    print("ETAPE 3 — Scoring explicable + decisions automatiques")
    print("=" * 70)

    score = call("POST", "/iocs/scoring/run", {"ioc_ids": [], "only_status": None})
    if "_error" in score:
        return 1
    print(f"  scores calcules={score['scored']}  publication={score['published']}  "
          f"surveillance={score['monitored']}  rejet={score['rejected']}")
    for d in sorted(score["details"], key=lambda x: -(x["score"] or 0)):
        print(f"   {d['score']:3}/100  {d['decision']:8}  {d['value'][:45]}")
        print(f"        -> {d['explanation'][:150]}")

    # ---- 4. Stats ------------------------------------------------------
    print("\n" + "=" * 70)
    print("ETAPE 4 — Statistiques (100% issues de la base)")
    print("=" * 70)
    stats = call("GET", "/iocs/stats/dashboard")
    if "_error" in stats:
        return 1
    print(f"  total={stats['total_iocs']} actifs={stats['active_iocs']} "
          f"rejeteurs={stats['rejected_iocs']} expires={stats['expired_iocs']} "
          f"synthetiques={stats['synthetic_iocs']}")
    print(f"  par type:  {stats['by_type']}")
    print(f"  par etat:  {stats['by_status']}")
    print(f"  scores:    {stats['score_distribution']}")
    print(f"  dedup_rate={stats['dedup_rate']}  avg_score={stats['avg_score']}")

    # ---- 5. Cycle de vie trace ----------------------------------------
    print("\n" + "=" * 70)
    print("ETAPE 5 — Journal du cycle de vie (derniers evenements)")
    print("=" * 70)
    events = call("GET", "/iocs/lifecycle/events?limit=15")
    for e in events if isinstance(events, list) else []:
        frm = e["from_status"] or "START"
        print(f"  {frm:14} -> {e['to_status']:14} {e['reason'][:60]}")

    print("\nDEMO TERMINEE AVEC SUCCES")
    return 0


if __name__ == "__main__":
    sys.exit(main())
