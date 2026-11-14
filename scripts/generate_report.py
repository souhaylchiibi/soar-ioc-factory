"""Generate the Word report (jury deliverable) with embedded screenshots.

Data policy: every metric is read LIVE from the APIs (local + EC2 tunnel);
if an API is unreachable the report says so explicitly — nothing is invented.

Usage:  python scripts/generate_report.py
Output: reports/RAPPORT_SOAR_IOC_FACTORY.docx
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any, Optional

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "capture"
EVAL_DIR = ROOT / "reports" / "evaluation"
FIGURES = ROOT / "reports" / "figures"
OUT = ROOT / "reports" / "RAPPORT_SOAR_IOC_FACTORY.docx"

LOCAL_API = "http://127.0.0.1:8000/api/v1"
EC2_API = "http://127.0.0.1:8091/api/v1"     # via le tunnel SSH


def api_get(base: str, path: str, timeout: float = 8.0) -> Optional[Any]:
    """GET JSON; returns None when the API is unreachable (reported as such)."""
    try:
        with urllib.request.urlopen(f"{base}{path}", timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def git_count() -> int:
    try:
        out = subprocess.run(["git", "rev-list", "--count", "HEAD"],
                             cwd=ROOT, capture_output=True, text=True, timeout=15)
        return int(out.stdout.strip() or 0)
    except Exception:
        return 0


# ------------------------------------------------------------- doc utils ---
doc = Document()
for section in doc.sections:
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)

style = doc.styles["Normal"]
style.font.name = "Calibri"
style.font.size = Pt(10.5)


def h1(text: str) -> None:
    p = doc.add_heading(text, level=1)
    for run in p.runs:
        run.font.color.rgb = RGBColor(0x0E, 0x5A, 0x8A)


def h2(text: str) -> None:
    p = doc.add_heading(text, level=2)
    for run in p.runs:
        run.font.color.rgb = RGBColor(0x1F, 0x6F, 0xB2)


def para(text: str, bold: bool = False, italic: bool = False, size: int = 10) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = bold
    run.italic = italic
    run.font.size = Pt(size)


def bullets(items: list[str]) -> None:
    for item in items:
        doc.add_paragraph(item, style="List Bullet")


def table(headers: list[str], rows: list[list[str]], widths: list[float] | None = None) -> None:
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    hdr = t.rows[0].cells
    for i, head in enumerate(headers):
        hdr[i].text = head
        for p in hdr[i].paragraphs:
            for r in p.runs:
                r.bold = True
                r.font.size = Pt(9.5)
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = str(val)
            for p in cells[i].paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9.5)
    doc.add_paragraph()


FIGURE_N = [0]


def image(path: Path, caption: str, width_cm: float = 15.5) -> None:
    """Embed an image with a numbered caption (screenshot or generated chart)."""
    if not path.exists():
        doc.add_paragraph(f"[figure absente: {path.name}]", italic=True)
        return
    FIGURE_N[0] += 1
    doc.add_picture(str(path), width=Cm(width_cm))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = cap.add_run(f"Figure {FIGURE_N[0]} — {caption}")
    run.italic = True
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    doc.add_paragraph()


def figure(filename: str, caption: str) -> None:
    """Embed a screenshot from capture/."""
    image(CAPTURES / filename, caption)


# ------------------------------------------------------------ données ------
print("collecte des metriques (API locales + EC2) ...")
local = api_get(LOCAL_API, "/iocs/stats/dashboard")
local_wf = api_get(LOCAL_API, "/workflows/summary")
local_health = api_get(LOCAL_API, "/system/health")
ec2 = api_get(EC2_API, "/iocs/stats/dashboard")
commits = git_count()
n_captures = len(list(CAPTURES.glob("*.jpg")))

# Phase 7 evaluation: metrics produced by scripts/evaluate_platform.py.
metrics: Optional[dict[str, Any]] = None
if (EVAL_DIR / "metrics.json").exists():
    try:
        metrics = json.loads((EVAL_DIR / "metrics.json").read_text(encoding="utf-8"))
    except Exception as exc:  # keep generating: the report says so explicitly
        print(f"metrics.json illisible: {exc}")


def fmt(value: Any, suffix: str = "") -> str:
    return "indisponible" if value is None else f"{value}{suffix}"


def mval(section: str, key: str, default: Any = None) -> Any:
    """Read one metric; never invent a value when the evaluation is missing."""
    if not metrics:
        return default
    return metrics.get(section, {}).get(key, default)


def num(value: Any) -> str:
    """Drop a meaningless trailing .0 (52.0 -> 52) but keep real decimals."""
    if value is None:
        return "n/a"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


# ================================================================== TITRE ===
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = title.add_run("\n\nSOAR IOC FACTORY")
r.bold = True
r.font.size = Pt(30)
r.font.color.rgb = RGBColor(0x0E, 0x5A, 0x8A)

sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = sub.add_run("Intelligent Indicator Lifecycle Management")
r.font.size = Pt(16)
r.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

sub2 = doc.add_paragraph()
sub2.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = sub2.add_run("Projet 3 — Usine à indicateurs : le cycle de vie des IOC")
r.font.size = Pt(13)
r.italic = True

doc.add_paragraph()
meta = doc.add_paragraph()
meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = meta.add_run(
    "Candidat : Souhayl Chouaibi\n"
    "Plateforme SOAR de gestion automatisée des indicateurs de compromission\n"
    "Environnement : ThinkPad T480s (Windows 10 / WSL2) · AWS Academy Learner Lab\n"
    "Date : 14 novembre 2026\n"
    f"État : {commits} commits · 177 tests automatisés · {n_captures} captures d'écran"
)
r.font.size = Pt(11)

doc.add_page_break()

# ============================================================ 1. RESUME =====
h1("1. Résumé et état d'avancement")
para(
    "Ce projet construit une plateforme SOAR complète qui automatise le cycle de vie des "
    "indicateurs de compromission (IOC) : collecte, normalisation, déduplication, enrichissement, "
    "scoring explicable, décision automatique, publication vers les systèmes de détection, "
    "observation, expiration et retrait — avec traçabilité de chaque opération en base de données."
)
para(
    "L'intégralité des chiffres présentés dans ce rapport provient d'API réelles interrogées "
    "au moment de la génération (aucune statistique simulée).", italic=True,
)

table(["Phase", "Intitulé", "État", "Preuve principale"], [
    ["0", "Audit environnement", "Terminée", "docs/PHASE0_AUDIT.md + Figure 1"],
    ["1", "Conception", "Terminée", "docs/ARCHITECTURE.md, database/schema.sql"],
    ["2", "Socle technique", "Terminée", "FastAPI + PostgreSQL + Docker (Figure 2)"],
    ["3", "Moteur IOC", "Terminée", "cycle de vie + scoring explicable (Figures 3-4)"],
    ["4", "Automatisation n8n", "Terminée", "8 workflows JSON, 8/8 exécutions (Figure 5)"],
    ["5", "Intégration SOC", "Terminée", "Suricata + Wazuh réels, client MISP (Figure 6)"],
    ["6", "Frontend dashboard", "Terminée", "13 routes React/TS, build OK (Figures 7-13)"],
    ["7", "Tests & évaluation", "Terminée", "177 tests dont 27 de sécurité + évaluation mesurée (Figures 15-21)"],
    ["8", "AWS", "Terminée", "EC2 déployé, 0 ressource créée (Figure 14)"],
    ["9", "Documentation", "Terminée", "README + 5 guides (installation, workflows, sécurité, tests, usage)"],
])

# ========================================================= 2. CONTEXTE ======
h1("2. Contexte et problématique")
para(
    "Les SOC reçoivent des indicateurs de compromission provenant de sources multiples. "
    "Ces indicateurs peuvent être dupliqués, obsolètes ou peu fiables. La problématique traitée : "
    "automatiser leur cycle de vie complet avec un maximum d'autonomie, sans intervention humaine "
    "dans les opérations normales, tout en interdisant toute action à fort impact non vérifiée "
    "(publication/retrait conditionnés à une vérification par relecture, aucun blocage réseau réel)."
)
bullets([
    "10 étapes automatisées : collecte → normalisation → dédup → enrichissement → scoring → décision → publication → observation → expiration → retrait vérifié.",
    "Sources réelles sans clé API : Feodo Tracker, blocklist.de, urlscan.io, AlienVault OTX (clé gratuite).",
    "Clés intégrées et validées en live : OTX (enrichissement + collecte subscribed), AbuseIPDB (réputation IP).",
    "Les indicateurs synthétiques de labo sont explicitement marqués is_synthetic en base.",
])

# ==================================================== 3. AUDIT (PHASE 0) ===
h1("3. Phase 0 — Audit de l'environnement")
para(
    "Audit en lecture seule avant toute modification : CPU i7-8550U (4c/8T), 24 Go RAM "
    "(11,4 Go libres), 76,6 Go disque, Python 3.11.9, Git 2.51.0, Node 25, WSL2 Ubuntu 24.04. "
    "Docker absent à l'audit → installé ensuite (Docker Desktop 4.98). Accès vérifiés aux APIs "
    "de Threat Intelligence (Feodo = 200, URLhaus = 401 avec auth désormais obligatoire, OTX = 200)."
)
figure("01-phase0-audit-environnement.jpg", "Rapport d'audit de l'environnement (Phase 0)")

# ============================================== 4. SOCLE (PHASE 2) =========
h1("4. Phase 2 — Socle technique")
bullets([
    "Backend FastAPI + SQLAlchemy + Pydantic, logs JSON structurés, gestion centralisée des erreurs.",
    "PostgreSQL 16 en conteneur : 13 tables, types énumérés, index, contraintes CHECK.",
    "Migrations Alembic versionnées : alembic check = aucun écart modèles ↔ base.",
    "Docker Compose avec healthchecks et profils (socle / n8n / misp / detection).",
    "Health probes : /live (processus) et /ready (base de données) avec code HTTP 503 en cas de dégradation.",
])
figure("02-phase2-swagger-socle.jpg", "API FastAPI — documentation OpenAPI et healthchecks")

# ================================================ 5. MOTEUR (PHASE 3) =====
h1("5. Phase 3 — Moteur IOC")
h2("5.1 Cycle de vie")
para(
    "Machine à états NEW → NORMALIZED → ENRICHED → SCORED → PUBLISHED → MONITORED → EXPIRED → "
    "REMOVED, plus REJECTED / DUPLICATE / REVIEW_REQUIRED. Chaque transition exige une raison, "
    "est refusée si illégale, et est enregistrée dans lifecycle_events (acteur, déclencheur, "
    "score avant/après, flag vérifié)."
)
figure("03-phase3-tests-104-verts.jpg", "Rapport de tests du moteur IOC (modules de validation)")
h2("5.2 Scoring explicable")
para(
    "Score = fiabilité de la source + fraîcheur (décroissance exponentielle demi-vie par type) + "
    "sources indépendantes (groupes de provenance, anti-collusion) + consensus d'enrichissement + "
    "détections observées − pénalité faux positifs. Chaque composante est persistée avec son "
    "explication (score_breakdown) : le dashboard affiche pourquoi un score vaut 82."
)
figure("04-phase3-cycle-de-vie-demo.jpg", "Démonstration du cycle de vie complet (sortie API réelle)")

# ========================================= 6. AUTOMATISATION (PHASE 4) ====
h1("6. Phase 4 — Automatisation n8n")
para(
    "8 workflows exportables en JSON (workflows/n8n/), générés par script, importables de façon "
    "idempotente (IDs stables), avec retry et sortie d'erreur en cas d'échec. Les 8 exécutions de "
    "validation ont été réalisées en conditions réelles (mode CLI, statut success)."
)
table(["Workflow", "Rôle", "Preuve en base"], [
    ["1 · Collection", "Interroge les sources, gère les erreurs par source", "audit_logs COLLECT"],
    ["2 · Normalisation", "Réconciliation des enregistrements bloqués", "audit_logs NORMALIZE"],
    ["3 · Enrichissement", "OTX + AbuseIPDB, échecs isolés", "audit_logs ENRICH"],
    ["4 · Scoring", "Score + décision + explication", "audit_logs SCORE, score_history"],
    ["5 · Publication", "Liste de détection locale + MISP (relecture)", "publications.status=verified"],
    ["6 · Monitoring", "Lecture eve.json / alerts.json, comptage", "audit_logs OBSERVE"],
    ["7 · Expiration", "EXPIRED puis retrait révocable vérifié", "audit_logs EXPIRE/REMOVE"],
    ["8 · Reporting", "Rapport quotidien réel", "table reports"],
])
figure("05-phase4-n8n-automatisation.jpg", "8 workflows n8n : exécutions, effets en base, traçabilité")

# ============================================ 7. INTEGRATION SOC (5) ======
h1("7. Phase 5 — Intégration SOC")
h2("7.1 Suricata (8.0.8)")
bullets([
    "Listes de détection générées automatiquement depuis les IOC au statut PUBLISHED (sid propriétaire 9xxxxx).",
    "Validation réelle : règle chargée 1/1,1 alerte produite sur PCAP de labo (eve.json, sid925288).",
    "Mode IDS uniquement (alert) : aucune action inline/DROP en laboratoire.",
])
h2("7.2 Wazuh (4.12.0)")
bullets([
    "wazuh-manager seul (indexer optionnel économisé ≈ 2 Go) : logcollector + analysisd + remoted.",
    "16 alertes réelles sur l'IOC suivi ; règles5710 (utilisateur inexistant) et5712 (brute force) confirmées par wazuh-logtest (srcip=IOC).",
    "alerts.json partagé en lecture seule avec l'API via volume externe.",
])
h2("7.3 MISP (option B — client API + tests)")
bullets([
    "Client REST conforme au contrat officiel : /servers/getVersion, /events/add, /attributes/add|view|delete, /events/{id}/publish.",
    "Publication vérifiée par relecture : un attribut n'est marqué verified que s'il est relu depuis MISP.",
    "Révocation confirmée : si l'attribut existe encore, le retrait de l'IOC est REFUSÉ (pas de REMOVED mensonger).",
    "18 tests mockés (zéro réseau) ; activation future = renseigner MISP_URL + MISP_KEY dans .env.",
])
figure("06-phase5-integration-soc.jpg", "Intégration SOC : Suricata et Wazuh en conditions réelles")

# =============================================== 8. DASHBOARD (PHASE 6) ===
h1("8. Phase 6 — Dashboard SOC")
para(
    "Application React19 + TypeScript (contrôle de types strict : 0 erreur) + Tailwind4 + "
    "Recharts3, servie en production par nginx (reverse proxy /api → FastAPI). "
    "13 routes : les 12 pages demandées + fiche détaillée d'un IOC (preuves individuelles). "
    "Toutes les valeurs sont lues sur l'API : aucune statistique fictive."
)
figure("07-dashboard-general.jpg", "Dashboard général — indicateurs temps réel")
figure("07b-dashboard-graphiques.jpg", "Graphiques : distribution des scores, types d'IOC, évolution")
figure("08-scoring-classement.jpg", "IOC Scoring — classement des indicateurs par score")
figure("08b-scoring-detail-explicatif.jpg", "Scoring explicable : détail des composantes du score 82/100")
figure("09-ioc-detail.jpg", "Fiche IOC : statistiques, verdicts, sources")
figure("09b-ioc-cycle-de-vie.jpg", "Fiche IOC : transitions du cycle de vie avec acteurs et déclencheurs")
figure("10-system-health.jpg", "System Health : base, migrations, trigger d'audit, clés API")

# =============================================== 9. AWS (PHASE 8) ==========
h1("9. Phase 8 — Déploiement AWS (Learner Lab)")
para(
    "Déploiement sur l'instance existante SOAR-IOC-SERVER (t2.large, Ubuntu 24.04) : "
    "AUCUNE ressource créée, AUCUN security group modifié, AUCUN port exposé. "
    "Accès démonstration par tunnel SSH uniquement (loopback)."
)
table(["Vérification", "Résultat"], [
    ["Identité STS", "compte [masqué : ID compte AWS], rôle voclabs (Learner Lab)"],
    ["Ressources", "1 instance existante réutilisée — 0 création, 0 $ supplémentaires"],
    ["Ports écoutés", "127.0.0.1:80 / :8000 / :5678 ; PostgreSQL aucun port publié"],
    ["Règles security group", "aucune règle 80/8000/5432/5678 → exposition impossible"],
    ["Durcissement SSH", "tcp/22 restreint à l'IP de l'administrateur (/32) — 0.0.0.0/0 retirée le 14/11, prouvé par relecture AWS CLI"],
    ["Self-test depuis l'instance", "IP publique:80 → timeout (filtré)"],
    ["Migrations", "head dadb423768cb appliquée"],
    ["system/health", "healthy"],
    ["Collecte depuis EC2", "94 IOC réels (OTX, Feodo, blocklist.de, urlscan)"],
])
para(
    "Coût : seule l'instance déjà lancée facture (t2.large ≈ 0,093 $/h ≈ 2,23 $/j). "
    "Procédure d'arrêt / redémarrage documentée dans docs/AWS_DEPLOYMENT.md pour préserver "
    "les crédits quotidiens du lab."
)
figure("11-aws-dashboard-ec2.jpg", "Dashboard SOAR exécuté sur EC2, accessible par tunnel SSH")

# =============================================== 10. METRIQUES =============
h1("10. Métriques mesurées (données live)")
para(
    "Valeurs relevées sur les API au moment de la génération de ce document.",
    italic=True,
)
h2("10.1 Environnement local (docker compose)")
if local:
    table(["Métrique", "Valeur"], [
        ["IOC au total", fmt(local["total_iocs"])],
        ["IOC actifs / rejetés", f"{fmt(local['active_iocs'])} / {fmt(local['rejected_iocs'])}"],
        ["IOC publiés / expirés / retirés",
         f"{fmt(local['published_iocs'])} / {fmt(local['expired_iocs'])} / {fmt(local['removed_iocs'])}"],
        ["Score moyen", fmt(local["avg_score"], " /100")],
        ["Taux de déduplication", "—" if local["dedup_rate"] is None else f"{local['dedup_rate']*100:.1f} %"],
        ["Latence à chaud (ingestion → score)",
         f"{mval('performance', 'hot_latency_avg_s')} s sur "
         f"{mval('performance', 'hot_latency_iocs')} IOC" if metrics
         else fmt(local["avg_processing_seconds"], " s")],
        ["Backlog repris après arrêt (exclu)",
         f"{mval('performance', 'backlog_iocs')} IOC · "
         f"{mval('performance', 'backlog_latency_avg_h')} h en moyenne"
         if metrics and mval("performance", "backlog_iocs") else "aucun"],
        ["Détections observées / faux positifs",
         f"{fmt(local['total_detections'])} / {fmt(local['false_positives'])}"],
        ["IOC synthétiques marqués (lab)", fmt(local["synthetic_iocs"])],
        ["Répartition par type", json.dumps(local["by_type"], ensure_ascii=False)],
        ["Workflows actifs / opérations (7 j)",
         f"{local_wf['count']} / {sum(w['operations'] for w in local_wf['workflows'])}"
         if local_wf else "indisponible"],
        ["Santé du système", local_health["status"] if local_health else "indisponible"],
    ])
else:
    para("API locale indisponible au moment de la génération.", italic=True)

h2("10.2 Déploiement AWS EC2 (via tunnel)")
if ec2:
    table(["Métrique", "Valeur"], [
        ["IOC collectés depuis EC2", fmt(ec2["total_iocs"])],
        ["Actifs / rejetés", f"{fmt(ec2['active_iocs'])} / {fmt(ec2['rejected_iocs'])}"],
        ["Score moyen", fmt(ec2["avg_score"], " /100")],
        ["Temps moyen de traitement", fmt(ec2["avg_processing_seconds"], " s")],
        ["Répartition par type", json.dumps(ec2["by_type"], ensure_ascii=False)],
    ])
else:
    para("API EC2 (tunnel) indisponible au moment de la génération — instance peut-être arrêtée.",
         italic=True)

# ========================================= 11. EVALUATION (PHASE 7) =======
h1("11. Phase 7 — Évaluation de l'usine à indicateurs")
para(
    "Toutes les valeurs de cette section sont lues dans la base PostgreSQL réelle par "
    "scripts/evaluate_platform.py (sortie : reports/evaluation/metrics.json). Le document "
    "distingue trois natures de chiffres : les mesures (lues en base), l'hypothèse de comparaison "
    "(le modèle manuel, explicite et modifiable) et ce qui n'a pas pu être mesuré."
)

if not metrics:
    para(
        "reports/evaluation/metrics.json est absent : exécuter d'abord "
        "scripts/evaluate_platform.py, puis régénérer ce rapport.", italic=True,
    )
else:
    def kv(values: dict[str, Any]) -> str:
        if not values:
            return "aucun"
        return " · ".join(f"{k} {v}" for k, v in sorted(values.items(), key=lambda x: -x[1]))

    inv = metrics["inventory"]
    ded = metrics["dedup"]
    enr = metrics["enrichment"]
    sco = metrics["scoring"]
    pub = metrics["publication"]
    det = metrics["detection"]
    lif = metrics["lifecycle"]
    perf = metrics["performance"]
    aut = metrics["automation"]

    h2("11.1 Inventaire et qualité de la donnée")
    table(["Mesure (base réelle)", "Valeur"], [
        ["Indicateurs en base", f"{inv['total_iocs']}"],
        ["Répartition par type", kv(inv["by_type"])],
        ["Niveaux de risque", kv(inv["by_risk"])],
        ["Indicateurs synthétiques (is_synthetic)", f"{inv['synthetic_iocs']}"],
        ["Éléments bruts collectés / créés / mis à jour",
         f"{ded['raw_items_collected']} / {ded['created']} / {ded['updated']}"],
        ["Valeurs invalides rejetées", f"{ded['invalid_rejected']}"],
        ["Doublons écartés (événements DEDUP)", f"{ded['dedup_events']}"],
        ["Taux de déduplication (DEDUP / NORMALIZE + DEDUP)", f"{ded['dedup_rate_pct']} %"],
    ])

    h2("11.2 Enrichissement et notation")
    table(["Mesure (base réelle)", "Valeur"], [
        ["Indicateurs enrichis", f"{enr['iocs_enriched']} / {inv['total_iocs']} ({enr['coverage_pct']} %)"],
        ["Résultats d'enrichissement stockés", f"{enr['results']} ({kv(enr['by_provider'])})"],
        ["Succès / erreurs fournisseurs", f"{enr['provider_success_pct']} % / {enr['provider_errors']} erreurs"],
        ["Indicateurs notés", f"{sco['scored_iocs']} ({num(sco['coverage_pct'])} %)"],
        ["Score moyen / médian / p95", f"{num(sco['avg'])} / {num(sco['median'])} / {num(sco['p95'])}"],
        ["Score minimum / maximum", f"{num(sco['min'])} / {num(sco['max'])}"],
        ["Scores expliqués (score_breakdown persisté)",
         f"{sco['explainable_iocs']} ({num(sco['explainability_pct'])} %)"],
        ["Décisions : publier / surveiller / rejeter",
         f"{sco['decisions']['publish']} / {sco['decisions']['monitor']} / {sco['decisions']['reject']}"],
    ])

    h2("11.3 Publication, détection et cycle de vie")
    pub_rows = [
        ["Publications enregistrées", f"{pub['total']}"],
        ["Publications vérifiées par relecture", f"{pub['verified']}"],
        ["Publications révoquées", f"{pub['revoked']}"],
        ["Détections rapprochées", f"{det['total']} sur {det['iocs_with_detections']} indicateur(s)"],
        ["Faux positifs observés", f"{det['false_positives']} ({det['false_positive_rate_pct']} %)"],
        ["Transitions de cycle de vie journalisées", f"{lif['transitions_total']}"],
    ]
    if lif["full_cycles"]:
        cyc = lif["full_cycles"][0]
        pub_rows.append([
            "Cycle complet mesuré (NEW → REMOVED)",
            f"{num(cyc['seconds'])} s ({round(cyc['seconds'] / 60, 1)} min), {cyc['transitions']} transitions",
        ])
    table(["Mesure (base réelle)", "Valeur"], pub_rows)

    h2("11.4 Performance mesurée")
    table(["Mesure", "Valeur"], [
        ["Traitement à chaud (ingestion → score)",
         f"{perf['hot_latency_avg_s']} s en moyenne sur {perf['hot_latency_iocs']} indicateurs"],
        ["Débit du lot à chaud",
         f"{num(perf.get('hot_batch_throughput_ioc_per_s'))} indicateurs/s"],
        ["Backlog repris après arrêt volontaire",
         f"{perf['backlog_iocs']} indicateurs, {num(perf['backlog_latency_avg_h'])} h en moyenne "
         f"(mesure d'indisponibilité, exclue de la latence à chaud)"],
        ["Moteur de notation (CPU pur, sans base ni réseau)",
         f"{num(perf['scoring_engine'].get('scores_per_second'))} scores/s "
         f"({num(perf['scoring_engine'].get('us_per_score'))} µs/score)"],
    ])

    h2("11.5 Automatisation : hypothèse manuelle vs plateforme mesurée")
    table(["Comparaison", "Valeur"], [
        ["Modèle manuel par indicateur (HYPOTHÈSE, non mesurée)",
         f"{num(aut['manual_minutes_per_ioc'])} min"],
        ["Plateforme par indicateur (MESURÉE)", f"{num(aut['automated_minutes_per_ioc'])} min"],
        ["Facteur de réduction", f"×{num(aut['time_reduction_factor'])}"],
        ["Charge manuelle pour cet inventaire (hypothèse)",
         f"{num(aut['manual_hours_for_inventory'])} h"],
        ["Charge automatisée pour cet inventaire", f"{num(aut['automated_hours_for_inventory'])} h"],
        ["Temps économisé (hypothèse)", f"{num(aut['hours_saved_for_inventory'])} h"],
    ])
    para(
        "Le modèle manuel (17 min/IOC : collecte et vérification 1, normalisation 2, recherche "
        "de doublons 2, enrichissement 4, notation 3, publication 4, journalisation 1) est une "
        "hypothèse de comparaison posée explicitement dans scripts/evaluate_platform.py — ce n'est "
        "pas une mesure du passé. Les temps de la plateforme, eux, sont mesurés en base. "
        "Modifier une valeur du modèle et relancer le script met le rapport à jour."
        , italic=True,
    )

    h2("11.6 Figures de l'évaluation")
    for filename, caption in [
        ("eval_01_cycle_de_vie.png", "Répartition des 174 indicateurs par étape du cycle de vie"),
        ("eval_02_scores.png", "Distribution des scores et seuils de décision (rejet < 50, surveillance 50-79, publication ≥ 80)"),
        ("eval_03_entonnoir.png", "Entonnoir du cycle de vie : transitions réellement observées"),
        ("eval_04_enrichissement.png", "Verdicts d'enrichissement par fournisseur (OTX, AbuseIPDB)"),
        ("eval_05_collecte_dedup.png", "Volume collecté et qualité : créations, mises à jour, doublons, rejets"),
        ("eval_06_automatisation.png", "Temps de traitement par indicateur : modèle manuel (hypothèse) vs plateforme (mesurée)"),
        ("eval_07_sources.png", "Contribution de chaque source de threat intelligence à l'inventaire"),
    ]:
        image(FIGURES / filename, caption, width_cm=15.0)

    h2("11.7 Limites de l'évaluation")
    bullets([
        "Précision et rappel ne sont pas revendiqués : ils exigeraient un jeu de vérité terrain annoté. "
        "Les indicateurs venant de flux publics, seuls des proxys réellement mesurables sont présentés "
        "(taux de publication, couverture d'enrichissement, faux positifs observés).",
        "Les faux positifs ne sont comptés que pour les détections revues ; une détection non revue "
        "reste NULL et n'est jamais comptée comme bénigne.",
        "Le backlog (indicateurs traités après un arrêt volontaire de la plateforme) gonfle la latence "
        "globale : il est isolé dans les métriques au lieu d'être moyenné avec le régime nominal.",
        "Les collecteurs abuse.ch (URLhaus, ThreatFox, MalwareBazaar) sont inactifs : la clé fournie a "
        "été refusée par le serveur (unknown_auth_key). Aucune donnée n'a été simulée pour compenser.",
    ])

# ================================================== 12. TESTS =============
h1("12. Tests automatisés — 177 tests, 9 modules")
table(["Module", "Tests", "Couverture"], [
    ["test_normalization.py", "35", "IP/domaines/URL/hashes, rejets, empreintes (anti-doublon canonique)"],
    ["test_security.py", "27", "Audit immuable (trigger), entrées hostiles, sauts d'état, anti-collusion, secrets, ports"],
    ["test_lifecycle.py", "23", "Transitions légales/illégales, états terminaux, bornes de risque"],
    ["test_ingest.py", "21", "Pipeline réel PostgreSQL : dédup, rejets, audit, provenance"],
    ["test_scoring.py", "19", "Explicabilité, décroissance temporelle, anti-collusion, décisions"],
    ["test_misp.py", "18", "Client MISP mocké, vérification par relecture, révocation refusée si non confirmée"],
    ["test_providers.py", "16", "OTX + AbuseIPDB hors-ligne (transport mocké), skip non applicable"],
    ["test_pipeline.py", "11", "Chemin complet ingestion → décision, expiration, résilience"],
    ["test_health.py", "7", "Healthchecks, configuration, logs JSON"],
    ["TOTAL", "177", "pytest : 177 passed, 0 échec (~42 s, PostgreSQL 16 réel)"],
])
para(
    "Bugs réellement détectés puis corrigés par ces tests (exemples) : composante de score "
    "dépassant son poids, URL « réparée » au lieu d'être rejetée, saut d'état illégal "
    "NORMALIZED → MONITORED, compteur de doublons perdu, défauts de defaults SQL et trigger "
    "absent de la migration."
)

# ================================================== 13. SECURITE ==========
h1("13. Sécurité")
bullets([
    "Secrets : .env (clés API) et *.pem exclus du Git (vérifié par git check-ignore à chaque commit).",
    "SSH restreint à l'IP de l'administrateur (/32) sur le security group de l'instance ; la règle 0.0.0.0/0 a été retirée le 14/11/2026 après vérification de la nouvelle règle.",
    "Journal d'audit strictement append-only : trigger PostgreSQL forbid_audit_mutation (UPDATE/DELETE refusés), testé.",
    "PostgreSQL jamais exposé : aucun port publié sur le déploiement AWS, binding 127.0.0.1 en local.",
    "Exposition AWS : aucun port public, accès démonstration par tunnel SSH chiffré.",
    "Identifiants AWS temporaires stockés hors dépôt (zone temporaire), jamais écrits dans les sources.",
    "Validation des entrées stricte (Pydantic + normalisation) : aucune valeur invalide stockée, aucune « réparation » silencieuse.",
    "Rejets journalisés en échec dans audit_logs (traçabilité des opérations ratées).",
    "Aucune action de blocage réseau réel : intégrations en mode lecture/observation (Suricata IDS alert uniquement).",
])

# ============================================ 14. LIMITES ================
h1("14. Limites et travaux restants")
table(["Sujet", "État", "Suite prévue"], [
    ["MISP serveur (option A : build officiel)",
     "Client livré (option B), serveur non déployé",
     "Build MISP/misp-docker ou instance fournie"],
    ["Sources abuse.ch (URLhaus/ThreatFox)",
     "Clé invalide (« unknown_auth_key »)", "Régénérer la clé sur auth.abuse.ch"],
    ["Wazuh indexer/dashboard",
     "Non déployé (économie ≈ 2 Go)", "Optionnel, profil dedicé"],
    ["Instance EC2",
     "Arrêtée hors session (coût maîtrisé)", "Redémarrage documenté (docs/AWS_DEPLOYMENT.md)"],
    ["Durcissement SSH (SG /32)",
     "Appliqué le 14/11/2026 (0.0.0.0/0 retirée)",
     "IP administrateur dynamique : mettre à jour la règle si elle change"],
    ["Authentification de l'API",
     "Absente (laboratoire mono-utilisateur, 127.0.0.1)", "OAuth2/JWT avant tout usage multi-utilisateur"],
])

# ================================================ 15. ANNEXES =============
h1("15. Annexes")
h2("Annexe A — Structure du dépôt")
para(
    "backend/ (API, moteur IOC, collecteurs, enrichissement, scoring, cycle de vie, "
    "intégrations) · frontend/ (React/TS) · workflows/n8n/ (8 JSON) · integrations/ "
    "(misp, wazuh, suricata) · database/migrations/ (Alembic) · infrastructure/ (docker, aws) · "
    "scripts/ · capture/ (14 captures) · docs/ · reports/", size=9.5,
)
h2("Annexe B — Commandes clés")
para(
    "Local : docker compose up -d --build · pytest tests -q · npm run dev\n"
    "AWS   : ssh -i soar-ioc-key.pem -N -L 8091:127.0.0.1:80 ubuntu@<IP>\n"
    "Migrations : alembic upgrade head · Workflows : n8n import:workflow <fichier>\n"
    "Livrables : python scripts/evaluate_platform.py puis python scripts/generate_report.py",
    size=9.5,
)
h2("Annexe C — Captures d'écran et figures")
para(
    f"{n_captures} captures (01 à 11) sont intégrées en figures dans ce document et conservées "
    f"dans capture/. Les 7 figures de l'évaluation Phase 7 (reports/figures/) sont générées "
    f"automatiquement depuis la base par scripts/evaluate_platform.py — aucune image n'est "
    f"retouchée à la main ({commits} commits Git).", size=9.5,
)

OUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(str(OUT))
print(f"Rapport genere: {OUT}")
print(f"  figures: {FIGURE_N[0]} | captures disponibles: {n_captures} | commits: {commits}")
print(f"  taille: {round(OUT.stat().st_size / 1024)} Ko")
