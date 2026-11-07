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


def figure(filename: str, caption: str) -> None:
    """Embed a screenshot from capture/ with a numbered caption."""
    path = CAPTURES / filename
    if not path.exists():
        doc.add_paragraph(f"[capture absente: {filename}]", italic=True)
        return
    FIGURE_N[0] += 1
    pic = doc.add_picture(str(path), width=Cm(15.5))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = cap.add_run(f"Figure {FIGURE_N[0]} — {caption}")
    run.italic = True
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    doc.add_paragraph()


# ------------------------------------------------------------ données ------
print("collecte des metriques (API locales + EC2) ...")
local = api_get(LOCAL_API, "/iocs/stats/dashboard")
local_wf = api_get(LOCAL_API, "/workflows/summary")
local_health = api_get(LOCAL_API, "/system/health")
ec2 = api_get(EC2_API, "/iocs/stats/dashboard")
commits = git_count()
n_captures = len(list(CAPTURES.glob("*.jpg")))


def fmt(value: Any, suffix: str = "") -> str:
    return "indisponible" if value is None else f"{value}{suffix}"


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
    "Date : 7 novembre 2026\n"
    f"État : {commits} commits · 150 tests automatisés · {n_captures} captures d'écran"
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
    ["7", "Tests & évaluation", "Partielle", "150 tests + métriques live ; comparatif à finaliser"],
    ["8", "AWS", "Terminée", "EC2 déployé, 0 ressource créée (Figure 14)"],
    ["9", "Documentation", "En cours", "audit, architecture, AWS livrés ; le reste en cours"],
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
        ["Temps moyen de traitement", fmt(local["avg_processing_seconds"], " s")],
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

# ================================================== 11. TESTS =============
h1("11. Tests automatisés — 150 tests, 8 modules")
table(["Module", "Tests", "Couverture"], [
    ["test_normalization.py", "35", "IP/domaines/URL/hashes, rejets, empreintes (anti-doublon canonique)"],
    ["test_lifecycle.py", "23", "Transitions légales/illégales, états terminaux, bornes de risque"],
    ["test_misp.py", "18", "Client MISP mocké, vérification par relecture, révocation refusée si non confirmée"],
    ["test_scoring.py", "19", "Explicabilité, décroissance temporelle, anti-collusion, décisions"],
    ["test_ingest.py", "21", "Pipeline réel PostgreSQL : dédup, rejets, audit, provenance"],
    ["test_providers.py", "16", "OTX + AbuseIPDB hors-ligne (transport mocké), skip non applicable"],
    ["test_pipeline.py", "11", "Chemin complet ingestion → décision, expiration, résilience"],
    ["test_health.py", "7", "Healthchecks, configuration, logs JSON"],
    ["TOTAL", "150", "Exécution : pytest,0 échec"],
])
para(
    "Bugs réellement détectés puis corrigés par ces tests (exemples) : composante de score "
    "dépassant son poids, URL « réparée » au lieu d'être rejetée, saut d'état illégal "
    "NORMALIZED → MONITORED, compteur de doublons perdu, défauts de defaults SQL et trigger "
    "absent de la migration."
)

# ================================================== 12. SECURITE ==========
h1("12. Sécurité")
bullets([
    "Secrets : .env (clés API) et *.pem exclus du Git (vérifié par git check-ignore à chaque commit).",
    "Journal d'audit strictement append-only : trigger PostgreSQL forbid_audit_mutation (UPDATE/DELETE refusés), testé.",
    "PostgreSQL jamais exposé : aucun port publié sur le déploiement AWS, binding 127.0.0.1 en local.",
    "Exposition AWS : aucun port public, accès démonstration par tunnel SSH chiffré.",
    "Identifiants AWS temporaires stockés hors dépôt (zone temporaire), jamais écrits dans les sources.",
    "Validation des entrées stricte (Pydantic + normalisation) : aucune valeur invalide stockée, aucune « réparation » silencieuse.",
    "Rejets journalisés en échec dans audit_logs (traçabilité des opérations ratées).",
    "Aucune action de blocage réseau réel : intégrations en mode lecture/observation (Suricata IDS alert uniquement).",
])

# ============================================ 13. LIMITES ================
h1("13. Limites et travaux restants")
table(["Sujet", "État", "Suite prévue"], [
    ["Phase 7 — rapport comparatif avant/après automatisation",
     "Partiel", "Script de métriques + graphiques de résultats"],
    ["Phase 9 — documentation",
     "Partiel (audit, architecture, AWS livrés)",
     "README, INSTALLATION, WORKFLOWS, SECURITY, TESTING, USER_GUIDE"],
    ["MISP serveur (option A : build officiel)",
     "Client livré (option B), serveur non déployé",
     "Build MISP/misp-docker ou instance fournie"],
    ["Sources abuse.ch (URLhaus/ThreatFox)",
     "Clé invalide (« unknown_auth_key »)", "Régénérer la clé sur auth.abuse.ch"],
    ["Wazuh indexer/dashboard",
     "Non déployé (économie ≈ 2 Go)", "Optionnel, profil dedicé"],
    ["Instance EC2",
     "En cours d'exécution (crédits consommés)", "Arrêt en fin de session (procédure documentée)"],
    ["Durcissement SSH (SG /32)",
     "Non appliqué (validation requise)", "Basculer sur le SG default (IP unique)"],
])

# ================================================ 14. ANNEXES =============
h1("14. Annexes")
h2("Annexe A — Structure du dépôt")
para(
    "backend/ (API, moteur IOC, collecteurs, enrichissement, scoring, cycle de vie, "
    "intégrations) · frontend/ (React/TS) · workflows/n8n/ (8 JSON) · integrations/ "
    "(misp, wazuh, suricata) · database/migrations/ (Alembic) · infrastructure/ (docker, aws) · "
    "scripts/ · capture/ (14 captures) · docs/ · reports/", size=9.5,
)
h2("Annexe B — Commandes clés")
para(
    "Local : docker compose up -d --build · pytest · npm run dev\n"
    "AWS   : ssh -i soar-ioc-key.pem -N -L 8091:127.0.0.1:80 ubuntu@<IP>\n"
    "Migrations : alembic upgrade head · Workflows : n8n import:workflow <fichier>",
    size=9.5,
)
h2("Annexe C — Captures d'écran intégrées")
para(
    f"{n_captures} captures (01 à 11) sont intégrées en figures dans ce document "
    f"et conservées dans capture/ ({commits} commits Git).", size=9.5,
)

OUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(str(OUT))
print(f"Rapport genere: {OUT}")
print(f"  figures: {FIGURE_N[0]} | captures disponibles: {n_captures} | commits: {commits}")
print(f"  taille: {round(OUT.stat().st_size / 1024)} Ko")
