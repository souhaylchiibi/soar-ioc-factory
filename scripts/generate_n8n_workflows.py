"""Generate the 8 n8n workflow JSON exports (workflows/n8n/*.json).

Design notes:
* every node has retry + error handling (`onError: continueErrorOutput`)
  so one failed HTTP call never kills the schedule,
* schedules are conservative (RAM-friendly) and documented in WORKFLOWS.md,
* the JSON is importable via `n8n import:workflow` (validated in Phase 4).
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[1] / "workflows" / "n8n"
API = "http://soar-api:8000/api/v1"


def _id() -> str:
    return str(uuid.uuid4())


def schedule(minutes: int | None = None, hours: int | None = None, day: str | None = None) -> dict:
    if day:  # daily at 06:00 UTC
        interval = [{"field": "days", "triggerAtDay": [day], "triggerAtHour": 6, "triggerAtMinute": 0}]
    elif hours:
        interval = [{"field": "hours", "hoursInterval": hours}]
    else:
        interval = [{"field": "minutes", "minutesInterval": minutes}]
    return {
        "parameters": {"rule": {"interval": interval}},
        "id": _id(), "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2,
        "position": [-460, 0],
    }


def manual_trigger() -> dict:
    """Manual start node.

    n8n's CLI (`n8n execute`) and the UI "Execute workflow" button only start
    from STARTING_NODES = [manualChatTrigger, manualTrigger] — a Schedule
    Trigger alone cannot be executed on demand. Both triggers are wired to
    the same first action, so scheduling is unaffected.
    """
    return {
        "parameters": {},
        "id": _id(), "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1,
        "position": [-460, 180],
    }


def http(name: str, method: str, url: str, body: dict | None = None,
         position: list[int] | None = None) -> dict:
    params: dict = {"method": method, "url": url, "options": {}, "sendHeaders": True,
                    "headerParameters": {"parameters": [
                        {"name": "Accept", "value": "application/json"}]}}
    if body is not None:
        params["sendBody"] = True
        params["specifyBody"] = "json"
        params["jsonBody"] = json.dumps(body)
    return {
        "parameters": params,
        "id": _id(), "name": name,
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
        "position": position or [40, 0],
        "retryOnFail": True, "maxTries": 3, "waitBetweenTries": 5000,
        "onError": "continueErrorOutput",
    }


def note(name: str, text: str, position: list[int]) -> dict:
    """Sticky note documenting the workflow inside n8n itself."""
    return {
        "parameters": {"content": text, "height": 160, "width": 340},
        "id": _id(), "name": name,
        "type": "n8n-nodes-base.stickyNote", "typeVersion": 1,
        "position": position,
    }


def chain(*nodes: dict, error_note: dict | None = None,
          extra_starts: list[dict] | None = None) -> dict:
    """Wire nodes linearly; expose the last node's error output if present.

    `extra_starts` are additional trigger nodes feeding the first node
    (e.g. Manual Trigger alongside Schedule Trigger).
    """
    connections: dict = {}
    first_name = nodes[0]["name"]
    for i, node in enumerate(nodes[:-1]):
        nxt = nodes[i + 1]["name"]
        entry = [[{"node": nxt, "type": "main", "index": 0}], []]
        connections[node["name"]] = {"main": entry}
    for start in (extra_starts or []):
        connections[start["name"]] = {
            "main": [[{"node": first_name, "type": "main", "index": 0}], []]
        }
    if error_note is not None:
        connections[nodes[-1]["name"]] = {
            "main": [[], [{"node": error_note["name"], "type": "main", "index": 0}]]
        }
    return {"connections": connections}


def build(name: str, description: str, nodes: list[dict], connections: dict,
          workflow_id: str | None = None) -> dict:
    wf = {
        "name": name,
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1", "timezone": "UTC",
                     "saveExecutionProgress": True},
        "active": False,   # imported inactive; activated explicitly after checks
        "meta": {"instanceId": "soar-ioc-factory"},
        "tags": [{"name": "soar-ioc-factory"}],
        "pinData": {},
        "_description": description,
    }
    if workflow_id:
        # Import with a fixed id -> replaces the existing workflow (no duplicate).
        wf["id"] = workflow_id
    return wf


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    workflows: list[tuple[str, dict]] = []

    # ---------------- Workflow 1 : IOC Collection ------------------------
    n1_err = note("On Error (collect)", "Erreur API / source inaccessible :\nretry 3x puis sortie d'erreur.\nL'echec est journalise dans audit_logs\n(success=false) — jamais un succes simule.", [-260, 260])
    nodes = [
        schedule(minutes=30),
        http("Collect from sources", "POST", f"{API}/iocs/collect/run?limit=50"),
        note("Doc", "Workflow 1 — Collecte periodique des IOC\nSources: Feodo Tracker, blocklist.de, urlscan.io\n(sans cle API) + gestion d'erreur isolee par source.", [-260, -240]),
        n1_err,
    ]
    conn = chain(nodes[0], nodes[1], error_note=n1_err)
    workflows.append(("01-ioc-collection", build(
        "1 - IOC Collection",
        "Collecte periodique depuis les sources de Threat Intelligence (sans cle API), "
        "normalisation et deduplication via l'API.",
        nodes, {**conn["connections"], "Doc": {}})))

    # ---------------- Workflow 2 : IOC Normalization ---------------------
    n2_err = note("On Error", "Echec -> retry puis sortie d'erreur\ntracee dans audit_logs.", [-260, 260])
    nodes = [
        schedule(minutes=30),
        http("Reconcile NEW records", "POST", f"{API}/iocs/normalize/run?limit=200"),
        note("Doc", "Workflow 2 — Normalisation + deduplication\nPasse de reconciliation pour les enregistrements\nbloques en NEW. Meme code que l'ingest:\nvalidation IP/domaine/URL/hash + empreinte.", [-260, -240]),
        n2_err,
    ]
    conn = chain(nodes[0], nodes[1], error_note=n2_err)
    workflows.append(("02-ioc-normalization", build(
        "2 - IOC Normalization",
        "Reconciliation de la normalisation et de la deduplication.",
        nodes, {**conn["connections"], "Doc": {}})))

    # ---------------- Workflow 3 : IOC Enrichment ------------------------
    n3_err = note("On Error", "Provider OTX inaccessible:\nretry 3x puis sortie d'erreur.\nUn provider en echec n'arrete jamais\nles autres (verdicts partages).", [-260, 260])
    nodes = [
        schedule(hours=1),
        http("Enrich via OTX", "POST", f"{API}/iocs/enrich/run?limit=50"),
        note("Doc", "Workflow 3 — Enrichissement OTX\nGET /indicators/{type}/{value}/general\nSans cle API. Verdict derive des donnees\nreelles (pulse_count) — jamais invente.", [-260, -240]),
        n3_err,
    ]
    conn = chain(nodes[0], nodes[1], error_note=n3_err)
    workflows.append(("03-ioc-enrichment", build(
        "3 - IOC Enrichment",
        "Enrichissement des IOC NORMALIZED via AlienVault OTX (public, sans cle).",
        nodes, {**conn["connections"], "Doc": {}})))

    # ---------------- Workflow 4 : IOC Scoring ---------------------------
    n4_err = note("On Error", "Echec du scoring -> retry puis\nsortie d'erreur tracee.", [-260, 260])
    nodes = [
        schedule(minutes=30),
        http("Score ENRICHED IOCs", "POST", f"{API}/iocs/scoring/run",
             body={"ioc_ids": [], "only_status": "ENRICHED"}),
        note("Doc", "Workflow 4 — Scoring explicable\nChaque score est stocke avec son detail\n(score_breakdown) dans score_history.\nSeuils: >=80 publier / 50-79 surveiller /\n<50 rejeter.", [-260, -240]),
        n4_err,
    ]
    conn = chain(nodes[0], nodes[1], error_note=n4_err)
    workflows.append(("04-ioc-scoring", build(
        "4 - IOC Scoring",
        "Calcul du score explicable et application des decisions automatiques.",
        nodes, {**conn["connections"], "Doc": {}})))

    # ---------------- Workflow 5 : IOC Publication -----------------------
    n5_err = note("On Error", "Publication echouee -> retry puis\nsortie d'erreur. L'API ne marque\n'verified' qu'apres relecture de la\npublication (jamais de succes auto-declare).", [-260, 280])
    nodes = [
        schedule(hours=1),
        http("Publish to detection list", "POST", f"{API}/iocs/publish/run?limit=100"),
        note("Doc", "Workflow 5 — Publication des IOC fiables\nCible actuelle: liste de detection locale.\nMISP arrive en Phase 5. Verification:\nrelecture apres ecriture (champ verified).", [-260, -240]),
        n5_err,
    ]
    conn = chain(nodes[0], nodes[1], error_note=n5_err)
    workflows.append(("05-ioc-publication", build(
        "5 - IOC Publication",
        "Publication des IOC a score eleve vers la liste de detection, avec verification.",
        nodes, {**conn["connections"], "Doc": {}})))

    # ---------------- Workflow 6 : IOC Monitoring ------------------------
    n6_err = note("On Error", "Capteurs injoignables -> retry puis\nsortie d'erreur tracee.", [-260, 260])
    nodes = [
        schedule(minutes=15),
        http("Fetch recent detections", "GET", f"{API}/iocs/detections/recent?limit=50"),
        note("Doc", "Workflow 6 — Observation des detections\nInterroge les evenements Wazuh/Suricata.\nCompte les correspondances et signale les\nfaux positifs (is_false_positive).", [-260, -240]),
        n6_err,
    ]
    conn = chain(nodes[0], nodes[1], error_note=n6_err)
    workflows.append(("06-ioc-monitoring", build(
        "6 - IOC Monitoring",
        "Surveillance des detections et des faux positifs.",
        nodes, {**conn["connections"], "Doc": {}})))

    # ---------------- Workflow 7 : IOC Expiration (2 etapes) -------------
    n7_err = note("On Error", "Echec retrait -> retry puis sortie\nd'erreur. REMOVED n'est pose qu'apres\nverification reelle de la reVocation.", [-260, 300])
    nodes = [
        schedule(hours=1),
        http("Step 1: mark EXPIRED", "POST", f"{API}/iocs/expire/run"),
        http("Step 2: revoke + REMOVED", "POST", f"{API}/iocs/remove/run"),
        note("Doc", "Workflow 7 — Expiration + retrait automatique\n1) marque EXPIRED les IOC dont expires_at est passe\n2) revoque les publications puis pose REMOVED\navec verification (verification_detail).", [-260, -260]),
        n7_err,
    ]
    conn = chain(nodes[0], nodes[1], nodes[2], error_note=n7_err)
    workflows.append(("07-ioc-expiration", build(
        "7 - IOC Expiration",
        "Expiration et retrait automatique des indicateurs obsolètes, avec verification.",
        nodes, {**conn["connections"], "Doc": {}})))

    # ---------------- Workflow 8 : IOC Reporting -------------------------
    n8_err = note("On Error", "Rapport non genere -> retry puis\nsortie d'erreur tracee.", [-260, 260])
    nodes = [
        schedule(day="mon,tue,wed,thu,fri,sat,sun"),
        http("Generate daily report", "POST", f"{API}/reports/daily"),
        note("Doc", "Workflow 8 — Rapport quotidien\nStatistiques reelles issues de PostgreSQL:\ncollected / published / rejected / expired,\nsources les plus utiles, dedup, faux positifs.", [-260, -240]),
        n8_err,
    ]
    conn = chain(nodes[0], nodes[1], error_note=n8_err)
    workflows.append(("08-ioc-reporting", build(
        "8 - IOC Reporting",
        "Generation quotidienne du rapport d'activite (statistiques reelles).",
        nodes, {**conn["connections"], "Doc": {}})))

    # ---- Write JSON files ------------------------------------------------
    # IDs already present in the n8n database: re-importing with the same id
    # REPLACES the workflow instead of creating a duplicate.
    EXISTING_IDS = {
        "01-ioc-collection": "m2O4V96oGzkZaiJl",
        "02-ioc-normalization": "jrbz74vokPzB9sNZ",
        "03-ioc-enrichment": "QxkfSR8uABSHOrOZ",
        "04-ioc-scoring": "ZjwJnGnWxeQoO8PS",
        "05-ioc-publication": "LqNcTCKxsoZl7Nkt",
        "06-ioc-monitoring": "FxFcs5nNMkJeXKEf",
        "07-ioc-expiration": "WCbwNKVMvYur4pDq",
        "08-ioc-reporting": "BcgzzjDErMHIM05i",
    }

    for fname, wf in workflows:
        # --- inject Manual Trigger (required for `n8n execute` + UI run) ---
        action = next(n for n in wf["nodes"] if n["type"] == "n8n-nodes-base.httpRequest")
        manual = manual_trigger()
        wf["nodes"].append(manual)
        wf["connections"][manual["name"]] = {
            "main": [[{"node": action["name"], "type": "main", "index": 0}], []]
        }
        # --- stable id -> idempotent re-import ---------------------------
        if fname in EXISTING_IDS:
            wf["id"] = EXISTING_IDS[fname]

        path = OUT_DIR / f"{fname}.json"
        path.write_text(json.dumps(wf, indent=2, ensure_ascii=False), encoding="utf-8")
        node_count = len(wf["nodes"])
        print(f"  {path.name:32} nodes={node_count} name='{wf['name']}'"
              f"{' id=' + wf['id'] if 'id' in wf else ''}")

    index = {
        "project": "SOAR IOC Factory",
        "generated_by": "scripts/generate_n8n_workflows.py",
        "api_base": API,
        "workflows": [
            {"file": f"{fname}.json", "name": wf["name"],
             "description": wf.get("_description", "")}
            for fname, wf in workflows
        ],
    }
    (OUT_DIR / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  index.json ({len(workflows)} workflows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
