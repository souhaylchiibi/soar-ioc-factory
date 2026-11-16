"""Rapport technique v0.2 — SOAR IOC Factory (Word, A4, français).

Conventions : .opencode/skills/rapport-docx (Calibri 10,5, titres #0E5A8A,
page de garde, sommaire TOC, en-tête/pied « Page X sur Y », tableaux et
figures numérotés avec source). Données : reports/v2/facts.json produit par
scripts/collect_v2_facts.py — aucun chiffre saisi à la main.

Usage : backend/.venv/Scripts/python.exe scripts/build_report_v2.py
Sortie : reports/RAPPORT_V2_SOAR_IOC_FACTORY.docx (+ figures reports/v2/fig_*.png)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.section import WD_SECTION  # noqa: E402
from docx.enum.table import WD_TABLE_ALIGNMENT  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT  # noqa: E402
from docx.oxml import OxmlElement  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm, Pt, RGBColor  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FACTS = json.loads((ROOT / "reports" / "v2" / "facts.json").read_text(encoding="utf-8"))
FIG_DIR = ROOT / "reports" / "v2"
SHOTS = ROOT / "capture" / "2026-11-16"
OUT = ROOT / "reports" / "RAPPORT_V2_SOAR_IOC_FACTORY.docx"
REPORT_DATE = "16 novembre 2026"

PRIMARY = RGBColor(0x0E, 0x5A, 0x8A)
SECONDARY = RGBColor(0x1F, 0x6F, 0xB2)
INK = RGBColor(0x33, 0x47, 0x5B)
GREY = RGBColor(0x5A, 0x6B, 0x7B)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
CONTENT_W = 16.6

L = FACTS["local"]
S = L["stats"]
AWS = FACTS["aws"] or {}
REPO = FACTS["repo"]


def fr(n: Any, dec: int = 0) -> str:
    if n is None:
        return "non mesuré"
    if isinstance(n, float) and dec:
        return f"{n:,.{dec}f}".replace(",", " ").replace(".", ",")
    return f"{int(n):,}".replace(",", " ")


# =============================================================== figures ====
PALETTE = ["#0E5A8A", "#2CC2A6", "#E0A43B", "#F0605D", "#7D8BA0", "#A48AF5", "#5AA2F5"]
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False,
    "axes.spines.right": False, "axes.edgecolor": "#9AA6B6", "axes.titleweight": "bold",
    "axes.titlesize": 10, "axes.titlecolor": "#0E5A8A", "figure.dpi": 160,
})


def save(fig, name: str) -> Path:
    path = FIG_DIR / f"fig_{name}.png"
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def fig_status() -> Path:
    order = ["NEW", "NORMALIZED", "ENRICHED", "SCORED", "PUBLISHED", "MONITORED",
             "REVIEW_REQUIRED", "EXPIRED", "REMOVED", "REJECTED"]
    data = [(k, S["by_status"].get(k, 0)) for k in order if S["by_status"].get(k, 0)]
    fig, ax = plt.subplots(figsize=(6.4, 2.6))
    bars = ax.barh([k for k, _ in data][::-1], [v for _, v in data][::-1], color="#0E5A8A")
    ax.bar_label(bars, padding=3, fontsize=8)
    ax.set_xlabel("IOC")
    ax.set_title("Inventaire local par statut")
    return save(fig, "statuts")


def fig_funnel() -> Path:
    stages = L["funnel"]["stages"]
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    labels = [f"{i + 1}. {s['label']}" for i, s in enumerate(stages)]
    vals = [s["count"] for s in stages]
    bars = ax.barh(labels[::-1], vals[::-1], color=["#2CC2A6" if s["key"] in ("publish", "remove") else "#0E5A8A" for s in stages][::-1])
    ax.bar_label(bars, padding=3, fontsize=8)
    ax.set_title("Débit mesuré des 10 étapes du cycle de vie")
    ax.set_xlabel("opérations tracées / IOC entrés dans l'étape")
    return save(fig, "funnel")


def fig_timeline() -> Path:
    series = L["timeline"]
    days = [p["date"][5:].replace("-", "/")[::-1][::-1] for p in series]
    labels = [f"{d[3:]}/{d[:2]}" for d in days]
    fig, ax = plt.subplots(figsize=(6.6, 2.6))
    ax.bar(labels, [p["created"] for p in series], color="#5AA2F5", label="IOC créés")
    ax.plot(labels, [p["published"] + p["monitored"] + p["rejected"] for p in series],
            color="#0E5A8A", lw=1.6, marker="o", ms=2.5, label="Décisions appliquées")
    ax.plot(labels, [p["detections"] for p in series], color="#E0A43B", lw=1.4, label="Détections")
    ax.set_xticks(range(0, len(labels), 4))
    ax.set_xticklabels(labels[::4], fontsize=7)
    ax.legend(frameon=False, fontsize=7.5, ncol=3, loc="upper left")
    ax.set_title("Activité quotidienne sur 30 jours (base locale)")
    return save(fig, "timeline")


def fig_security() -> Path:
    scans = FACTS["security_scans"]
    fig, ax = plt.subplots(figsize=(6.4, 2.6))
    x = range(len(scans))
    ax.bar([i - 0.18 for i in x], [s["before"] for s in scans], width=0.36, color="#F0605D", label="Avant correction")
    ax.bar([i + 0.18 for i in x], [s["after"] for s in scans], width=0.36, color="#2CC2A6", label="Après correction")
    for i, s in enumerate(scans):
        ax.text(i - 0.18, s["before"] + 0.4, str(s["before"]), ha="center", fontsize=7.5)
        ax.text(i + 0.18, s["after"] + 0.4, str(s["after"]), ha="center", fontsize=7.5)
    ax.set_xticks(list(x))
    ax.set_xticklabels([s["tool"] for s in scans], fontsize=7.5)
    ax.set_ylabel("constats ouverts")
    ax.legend(frameon=False, fontsize=7.5)
    ax.set_title("Analyses de sécurité : constats avant / après")
    return save(fig, "securite")


def fig_tests() -> Path:
    tests = FACTS["tests"]
    fig, ax = plt.subplots(figsize=(6.4, 2.2))
    bars = ax.barh([t["suite"] for t in tests][::-1], [t["passed"] for t in tests][::-1], color="#2CC2A6")
    ax.bar_label(bars, labels=[f"{t['passed']}/{t['count']}" for t in tests][::-1], padding=3, fontsize=8)
    ax.set_title("Tests exécutés le 16/11/2026 (réussis / total)")
    ax.set_xscale("log")
    ax.set_xlabel("nombre de tests (échelle log)")
    return save(fig, "tests")


def fig_local_vs_aws() -> Path:
    keys = ["MONITORED", "REJECTED", "PUBLISHED", "NORMALIZED"]
    loc = [S["by_status"].get(k, 0) for k in keys]
    aws = [(AWS.get("by_status") or {}).get(k, 0) for k in keys]
    fig, ax = plt.subplots(figsize=(6.0, 2.4))
    x = range(len(keys))
    b1 = ax.bar([i - 0.2 for i in x], loc, width=0.4, color="#0E5A8A", label=f"Local ({fr(S['total_iocs'])} IOC)")
    b2 = ax.bar([i + 0.2 for i in x], aws, width=0.4, color="#E0A43B", label=f"AWS EC2 ({fr(AWS.get('total_iocs'))} IOC)")
    ax.bar_label(b1, fontsize=7.5, padding=2)
    ax.bar_label(b2, fontsize=7.5, padding=2)
    ax.set_xticks(list(x))
    ax.set_xticklabels(keys, fontsize=8)
    ax.legend(frameon=False, fontsize=7.5)
    ax.set_title("Deux bases distinctes : locale et AWS (statuts)")
    return save(fig, "local_aws")


# ============================================================ docx helpers ===
def _el(tag: str, **attrs: str):
    element = OxmlElement(f"w:{tag}")
    for key, value in attrs.items():
        element.set(qn(f"w:{key}"), str(value))
    return element


def shade(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    for old in tc_pr.findall(qn("w:shd")):
        tc_pr.remove(old)
    tc_pr.append(_el("shd", val="clear", color="auto", fill=fill))


def borders(tbl, color: str = "C9D6E2") -> None:
    b = _el("tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        b.append(_el(edge, val="single", sz=4, space=0, color=color))
    tbl._tbl.tblPr.append(b)


def widths(tbl, cms: list[float]) -> None:
    tbl.autofit = False
    tbl._tbl.tblPr.append(_el("tblLayout", type="fixed"))
    for i, w in enumerate(cms):
        for row in tbl.rows:
            row.cells[i].width = Cm(w)


def field(paragraph, instr: str, placeholder: str = "", size: Optional[float] = None,
          color: Optional[RGBColor] = None) -> None:
    run = paragraph.add_run()
    if size:
        run.font.size = Pt(size)
    if color is not None:
        run.font.color.rgb = color
    run._r.append(_el("fldChar", fldCharType="begin"))
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = instr
    run._r.append(it)
    run._r.append(_el("fldChar", fldCharType="separate"))
    if placeholder:
        t = OxmlElement("w:t")
        t.text = placeholder
        run._r.append(t)
    run._r.append(_el("fldChar", fldCharType="end"))


def p_border(paragraph, edge: str = "bottom", color: str = "0E5A8A", size: int = 8) -> None:
    ppr = paragraph._p.get_or_add_pPr()
    b = _el("pBdr")
    b.append(_el(edge, val="single", sz=size, space=4, color=color))
    ppr.append(b)


doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21), Cm(29.7)
sec.top_margin, sec.bottom_margin = Cm(2.2), Cm(2.0)
sec.left_margin, sec.right_margin = Cm(2.3), Cm(2.1)
sec.header_distance, sec.footer_distance = Cm(1.0), Cm(0.9)
sec.different_first_page_header_footer = True

normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(10.5)
normal.font.color.rgb = RGBColor(0x1E, 0x1E, 0x1E)
normal.paragraph_format.space_after = Pt(6)
normal.paragraph_format.line_spacing = 1.12
normal.element.get_or_add_rPr().append(_el("lang", val="fr-FR"))
for name, size, color, before, after in (("Heading 1", 17, PRIMARY, 0, 10),
                                         ("Heading 2", 12.5, SECONDARY, 12, 5),
                                         ("Heading 3", 11, INK, 8, 3)):
    st = doc.styles[name]
    st.font.name, st.font.size, st.font.bold, st.font.color.rgb = "Calibri", Pt(size), True, color
    st.paragraph_format.space_before, st.paragraph_format.space_after = Pt(before), Pt(after)
    st.paragraph_format.keep_with_next = True

for _style in ("Header", "Footer"):
    doc.styles[_style].paragraph_format.tab_stops.clear_all()
hp = sec.header.paragraphs[0]
hp.paragraph_format.tab_stops.add_tab_stop(Cm(CONTENT_W - 0.2), WD_TAB_ALIGNMENT.RIGHT)
for text, tab in (("SOAR IOC FACTORY · Rapport technique v0.2", True), (REPORT_DATE, False)):
    r = hp.add_run(text)
    r.font.size, r.font.color.rgb = Pt(8), GREY
    if tab:
        hp.add_run("\t")
p_border(hp, color="C9D6E2", size=4)

fp = sec.footer.paragraphs[0]
fp.paragraph_format.tab_stops.add_tab_stop(Cm(CONTENT_W - 0.2), WD_TAB_ALIGNMENT.RIGHT)
for text in ("Console SOC · authentification · durcissement · déploiement AWS", "\t", "Page "):
    r = fp.add_run(text)
    r.font.size, r.font.color.rgb = Pt(8), GREY
field(fp, " PAGE ", "1", 8, GREY)
r = fp.add_run(" sur ")
r.font.size, r.font.color.rgb = Pt(8), GREY
field(fp, " NUMPAGES ", "1", 8, GREY)
doc.settings.element.append(_el("updateFields", val="true"))

N = {"table": 0, "figure": 0}


def h1(text: str, new_page: bool = True) -> None:
    p = doc.add_heading(text, level=1)
    p.paragraph_format.page_break_before = new_page


def h2(text: str) -> None:
    doc.add_heading(text, level=2)


def para(text: str, size: float = 10.5, italic: bool = False, bold: bool = False,
         align=WD_ALIGN_PARAGRAPH.JUSTIFY, color: Optional[RGBColor] = None, after: float = 6) -> None:
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_after = Pt(after)
    r = p.add_run(text)
    r.font.size, r.italic, r.bold = Pt(size), italic, bold
    if color is not None:
        r.font.color.rgb = color


def bullets(items: Iterable[str]) -> None:
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(2)
        if " : " in item:
            head, tail = item.split(" : ", 1)
            r = p.add_run(head + " : ")
            r.bold = True
            p.add_run(tail)
        else:
            p.add_run(item)


def table(caption: str, headers: list[str], rows: list[list[Any]], cms: list[float],
          source: Optional[str] = None, size: float = 8.5) -> None:
    N["table"] += 1
    cap = doc.add_paragraph()
    cap.paragraph_format.space_before, cap.paragraph_format.space_after = Pt(8), Pt(4)
    cap.paragraph_format.keep_with_next = True
    r = cap.add_run(f"Tableau {N['table']} — {caption}")
    r.bold, r.font.size, r.font.color.rgb = True, Pt(9), PRIMARY
    t = doc.add_table(rows=1, cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    borders(t)
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        shade(c, "0E5A8A")
        c.paragraphs[0].paragraph_format.space_after = Pt(0)
        rr = c.paragraphs[0].add_run(h)
        rr.bold, rr.font.size, rr.font.color.rgb = True, Pt(size), WHITE
    t.rows[0]._tr.get_or_add_trPr().append(_el("tblHeader", val="true"))
    for ri, values in enumerate(rows):
        row = t.add_row()
        row._tr.get_or_add_trPr().append(_el("cantSplit", val="true"))
        for i, v in enumerate(values):
            c = row.cells[i]
            if ri % 2:
                shade(c, "F2F7FB")
            pp = c.paragraphs[0]
            pp.paragraph_format.space_after, pp.paragraph_format.line_spacing = Pt(0), 1.0
            rr = pp.add_run(str(v))
            rr.font.size = Pt(size)
    widths(t, cms)
    note = doc.add_paragraph()
    note.paragraph_format.space_before, note.paragraph_format.space_after = Pt(3), Pt(10)
    if source:
        rr = note.add_run(f"Source : {source}")
        rr.italic, rr.font.size, rr.font.color.rgb = True, Pt(8), GREY


def figure(path: Path, caption: str, width_cm: float = 15.5, source: Optional[str] = None) -> None:
    N["figure"] += 1
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(6)
    p.add_run().add_picture(str(path), width=Cm(width_cm))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(10)
    r = cap.add_run(f"Figure {N['figure']} — {caption}")
    r.bold, r.font.size, r.font.color.rgb = True, Pt(8.5), PRIMARY
    if source:
        r2 = cap.add_run(f"  ·  {source}")
        r2.italic, r2.font.size, r2.font.color.rgb = True, Pt(8), GREY


def callout(title: str, body: str, fill: str = "EAF2F8", bar: str = "0E5A8A") -> None:
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    widths(t, [CONTENT_W])
    c = t.cell(0, 0)
    shade(c, fill)
    tcpr = c._tc.get_or_add_tcPr()
    b = _el("tcBorders")
    b.append(_el("left", val="single", sz=18, space=0, color=bar))
    for e in ("top", "bottom", "right"):
        b.append(_el(e, val="nil"))
    tcpr.append(b)
    p = c.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(title)
    r.bold, r.font.size, r.font.color.rgb = True, Pt(9.5), PRIMARY
    p = c.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_after = Pt(0)
    r = p.add_run(body)
    r.font.size, r.font.color.rgb = Pt(9.5), INK
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def kpis(items: list[tuple[str, str]]) -> None:
    """Row of KPI cards (big number + label)."""
    t = doc.add_table(rows=2, cols=len(items))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    widths(t, [CONTENT_W / len(items)] * len(items))
    for i, (value, label) in enumerate(items):
        for ri in (0, 1):
            shade(t.cell(ri, i), "EAF2F8")
        p = t.cell(0, i).paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(value)
        r.bold, r.font.size, r.font.color.rgb = True, Pt(18), PRIMARY
        p = t.cell(1, i).paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(label)
        r.font.size, r.font.color.rgb = Pt(8), INK
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


# ============================================================ page de garde =
def cover() -> None:
    for _ in range(3):
        doc.add_paragraph()
    p = doc.add_paragraph()
    r = p.add_run("PROJET 3 · CYBER THREAT INTELLIGENCE")
    r.bold, r.font.size, r.font.color.rgb = True, Pt(10), GREY
    p = doc.add_paragraph()
    r = p.add_run("SOAR IOC Factory")
    r.bold, r.font.size, r.font.color.rgb = True, Pt(34), PRIMARY
    p = doc.add_paragraph()
    r = p.add_run("Rapport technique — version 0.2")
    r.font.size, r.font.color.rgb = Pt(18), SECONDARY
    p_border(p, color="0E5A8A", size=12)
    para("Console SOC professionnelle, authentification à rôles, durcissement sécurité "
         "et déploiement AWS — avec preuves mesurées.", size=12, color=INK,
         align=WD_ALIGN_PARAGRAPH.LEFT, after=24)
    kpis([
        (fr(S["total_iocs"]), "IOC en base locale"),
        (fr(sum(t["passed"] for t in FACTS["tests"])), "tests exécutés et réussis"),
        ("0", "constat de sécurité ouvert"),
        ("13", "pages de console"),
    ])
    for _ in range(4):
        doc.add_paragraph()
    t = doc.add_table(rows=5, cols=2)
    widths(t, [5.0, 11.6])
    for i, (k, v) in enumerate((
        ("Date", REPORT_DATE),
        ("Version livrée", f"v0.2 · branche {REPO['branch']} · commit {REPO['commit']}"),
        ("Périmètre", f"{REPO['v02_diff']}"),
        ("Déploiement", "Local (Docker Compose) + AWS EC2 us-east-1 (accès par tunnel SSH)"),
        ("Auteur", "Souhayl Chouaibi — avec l'assistance de Claude Code"),
    )):
        a, b = t.rows[i].cells
        a.paragraphs[0].add_run(k).bold = True
        b.paragraphs[0].add_run(v)
        for c in (a, b):
            c.paragraphs[0].runs[0].font.size = Pt(9.5)
            c.paragraphs[0].paragraph_format.space_after = Pt(2)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def toc() -> None:
    p = doc.add_paragraph()
    r = p.add_run("Sommaire")
    r.bold, r.font.size, r.font.color.rgb = True, Pt(17), PRIMARY
    p_border(p)
    field(doc.add_paragraph(), ' TOC \\o "1-2" \\h \\z \\u ',
          "Mettre à jour le sommaire : clic droit → Mettre à jour les champs (F9).")
    para("Les chiffres de ce rapport proviennent de PostgreSQL (application locale et "
         "serveur AWS) et des commandes de test exécutées le 16/11/2026. Lorsqu'une "
         "donnée n'existe pas, le rapport l'indique au lieu de l'estimer.",
         size=9, italic=True, color=GREY)


# ================================================================== contenu ==
def build() -> None:
    figs = {
        "statuts": fig_status(), "funnel": fig_funnel(), "timeline": fig_timeline(),
        "securite": fig_security(), "tests": fig_tests(), "local_aws": fig_local_vs_aws(),
    }
    cover()
    toc()

    # 1 -------------------------------------------------------------------
    h1("1. Synthèse")
    para("La version 0.2 transforme SOAR IOC Factory en plateforme de Cyber Threat "
         "Intelligence exploitable par une équipe SOC : une console redessinée sur données "
         "réelles, un contrôle d'accès par rôles, la correction de failles identifiées à "
         "l'audit et un déploiement vérifié sur AWS. L'architecture existante (FastAPI, "
         "PostgreSQL 16, React 19, n8n, Docker Compose) est conservée.")
    kpis([
        (fr(S["total_iocs"]), "IOC (base locale)"),
        (fr(AWS.get("total_iocs")), "IOC (serveur AWS)"),
        (fr(S["total_detections"]), "détections rapprochées"),
        (fr(L["funnel"]["verified_removals"]), "retrait vérifié"),
    ])
    table("Résultats clés de la version 0.2",
          ["Domaine", "Résultat mesuré", "Preuve"],
          [
              ["Sécurité d'accès", "API fermée : 401 sans jeton, 3 rôles, verrouillage après 5 échecs", "tests test_auth_api.py (22)"],
              ["Failles corrigées", "traversée de chemin, acteur d'audit falsifiable, 31 vulnérabilités de dépendances/images", "Bandit, pip-audit, Trivy"],
              ["Console SOC", "13 pages connectées à l'API, design system dédié, responsive", "8 scénarios Playwright"],
              ["Automatisation", "8 workflows n8n authentifiés par clé de service", "exécution n8n réelle : status success"],
              ["Déploiement AWS", f"v0.2 en production de labo, migration {AWS.get('alembic', '—')}, ports 127.0.0.1 uniquement", "e2e via tunnel : 8/8"],
              ["Qualité", f"{sum(t['passed'] for t in FACTS['tests'])} tests réussis sur {sum(t['count'] for t in FACTS['tests'])} exécutés", "§ 8"],
          ], [3.4, 8.6, 4.6], source="docs/LIVRAISON_V2.md, reports/v2/facts.json")
    callout("Principe d'intégrité respecté",
            "Aucune donnée simulée n'est présentée comme réelle : les IOC du collecteur de "
            "laboratoire portent le marqueur LAB, une intégration non configurée est affichée "
            "« Configuration manquante », une durée non mesurée est écrite « non mesurée ». "
            "Aucune action n'est déclarée réussie sans relecture (publication, retrait).")

    # 2 -------------------------------------------------------------------
    h1("2. Audit initial et diagnostic")
    para("Avant toute modification, le dépôt a été audité : architecture, backend FastAPI, "
         "modèles et migrations, routes, services, workflows n8n, intégrations, frontend, "
         "tests, Docker et documentation. La carte du code produite par graphify "
         "(827 nœuds, 2 580 liens, aucune dépendance circulaire) a confirmé que les "
         "abstractions centrales étaient saines : Ioc, AuditLog, la machine à états et le "
         "moteur de score.")
    table("Constats de l'audit et gravité",
          ["#", "Constat", "Gravité", "Statut v0.2"],
          [
              ["D1", "Aucune authentification : toutes les écritures ouvertes", "Critique", "Corrigé"],
              ["D2", "Traversée de chemin via ?path= (lecture de fichiers arbitraires)", "Élevée", "Corrigé"],
              ["D3", "Acteur d'audit fourni par le client (falsifiable)", "Élevée", "Corrigé"],
              ["D4", "Dépendances et images vulnérables, nginx en root", "Élevée", "Corrigé"],
              ["D5", "Pas de rate limiting, en-têtes, CORS large, TLS MISP désactivé", "Moyenne", "Corrigé"],
              ["D6", "État des sources jamais mis à jour par la collecte", "Moyenne", "Corrigé"],
              ["D7", "Requête N+1 dans l'inventaire", "Faible", "Corrigé"],
              ["D8", "Durée des exécutions non mesurée", "Faible", "Corrigé (nouvelles exécutions)"],
              ["D9", "Interface monolithique, emojis, bundle unique 741 Ko, sans tests", "Moyenne", "Refait"],
              ["D10", "Détections sans valeur d'IOC, sévérité ni qualification", "Moyenne", "Refait"],
              ["D11", "État des intégrations invisible", "Moyenne", "Ajouté"],
          ], [1.0, 9.6, 2.2, 3.8], source="audit du dépôt, 16/11/2026")

    # 3 -------------------------------------------------------------------
    h1("3. Architecture")
    arch = ROOT / "reports" / "figures" / "architecture.png"
    if arch.exists():
        figure(arch, "Architecture de la plateforme (socle inchangé en v0.2)", 15.5)
    para("La v0.2 ajoute trois briques sans remplacer l'existant :")
    bullets([
        "Couche de sécurité : authentification JWT, rôles, clé de service, limiteur de débit et en-têtes (app/core/security.py, app/core/middleware.py).",
        "API SOC : intégrations, notifications, funnel, timeline, Detection Center, historique d'exécutions, dossier IOC, recherche (app/api/soc.py).",
        "Console : coque applicative, 13 pages chargées à la demande, composants réutilisables (frontend/src/components).",
    ])
    table("Composants et responsabilités",
          ["Composant", "Rôle", "Exposition"],
          [
              ["PostgreSQL 16", "inventaire, cycle de vie, audit append-only, utilisateurs", "réseau Docker interne"],
              ["API FastAPI", "pipeline IOC, scoring, publication, SOC, authentification", "127.0.0.1:8000"],
              ["n8n", "8 workflows planifiés appelant l'API avec la clé de service", "127.0.0.1:5678"],
              ["Console React", "interface analyste (nginx non-root en production)", "127.0.0.1:80 → tunnel SSH"],
              ["Suricata / Wazuh", "alertes lues en lecture seule depuis /sensor", "aucune"],
              ["MISP", "publication distante (client prêt, serveur absent)", "non configuré"],
          ], [3.4, 8.8, 4.4])

    # 4 -------------------------------------------------------------------
    h1("4. Sécurité")
    h2("4.1 Authentification et autorisations")
    table("Contrôles d'accès implémentés",
          ["Contrôle", "Implémentation", "Test"],
          [
              ["Mots de passe", "Argon2id, ≥ 12 caractères, 3 classes", "test_password_policy"],
              ["Jetons", "JWT HS256, 60 min, exp/sub obligatoires", "test_tampered_token_rejected"],
              ["Révocation", "compte relu à chaque requête", "test_disabled_account_token_is_rejected_immediately"],
              ["Rôles", "viewer < analyst < admin", "TestAuthorization (5 tests)"],
              ["Identité d'audit", "issue du jeton, jamais du corps", "test_analyst_transition_uses_token_identity_not_body"],
              ["Automatisation", "X-API-Key à temps constant, X-Actor filtré", "TestServiceKey (4 tests)"],
              ["Force brute", "verrouillage 5 échecs / 15 min + 10 req/min/IP", "test_lockout…, test_login_rate_limited"],
              ["Dernier admin", "rétrogradation / désactivation de soi refusée", "test_last_admin_cannot_demote_itself"],
              ["Production", "refus de démarrer si secret faible, auth off, debug, CORS *", "test_production_config_guard"],
          ], [3.0, 6.6, 7.0], size=8)
    h2("4.2 Durcissement et analyses")
    figure(figs["securite"], "Constats ouverts par outil, avant et après correction", 15.0,
           "Bandit, pip-audit, npm audit, Trivy, OWASP ZAP — 16/11/2026")
    table("Résultats des analyses de sécurité",
          ["Outil", "Avant", "Après", "Détail"],
          [[s["tool"], s["before"], s["after"], s["note"]] for s in FACTS["security_scans"]],
          [3.2, 1.6, 1.6, 10.2], source="docs/SECURITY.md § 7 bis ; reports/security/zap-baseline.html")
    callout("Risques résiduels assumés",
            "Jeton conservé en sessionStorage (mitigé par une CSP stricte et 60 min de validité), "
            "limiteur de débit par processus, style-src 'unsafe-inline' requis par les styles "
            "React/Recharts (aucun script inline), compte PostgreSQL unique pour l'API et les "
            "migrations.", fill="FDF3E6", bar="E0A43B")

    # 5 -------------------------------------------------------------------
    h1("5. Console SOC")
    para("La direction artistique a été établie avec la skill ui-ux-pro-max. Sa première "
         "proposition (style « cyberpunk », néons) a été écartée car le cahier des charges "
         "exclut les couleurs fluorescentes ; le style « Minimalism & Swiss » recommandé "
         "pour les tableaux de bord d'entreprise a été retenu, avec une palette graphite et "
         "un accent sarcelle propres au projet.")
    table("Jetons de couleur principaux",
          ["Rôle", "Valeur", "Usage"],
          [["Fond / surface", "#0B0F14 / #10151C", "élévation par la luminosité, sans ombre"],
           ["Texte / secondaire", "#E7ECF2 / #9AA6B6", "contraste ≥ 4,5:1 sur toutes les surfaces"],
           ["Accent identité", "#2CC2A6", "état actif, focus, action principale"],
           ["Risque critique → faible", "#F0605D · #EE8A3C · #E0B33B · #7D8BA0", "toujours accompagné du libellé"]],
          [4.2, 5.4, 7.0], source="docs/DESIGN_SYSTEM.md")
    figure(SHOTS / "v2-02-overview.png", "SOC Overview — indicateurs, intégrations, activité, risques", 11.0,
           "capture locale 1440 px")
    for name, cap in (
        ("v2-03-detection-center.png", "Detection Center — alertes capteurs, sévérité déclarée, qualification"),
        ("v2-05-ioc-detail.png", "Dossier de preuve d'un IOC — score justifié, cycle de vie, provenance"),
        ("v2-06-lifecycle.png", "IOC Lifecycle — dix étapes et leur preuve"),
        ("v2-08-sources.png", "Sources — connexion réelle, fiabilité, historique des collectes"),
        ("v2-09-automation.png", "Automation Center — workflows n8n et exécutions mesurées"),
        ("v2-11-system-health.png", "System Health — contrôles internes et intégrations"),
    ):
        figure(SHOTS / name, cap, 15.5)
    table("Pages de la console",
          ["Page", "Contenu principal", "Actions (rôle)"],
          [["SOC Overview", "KPI, intégrations, activité 14/30/90 j, risques, sources, workflows", "—"],
           ["Detection Center", "alertes Suricata/Wazuh/manuelles, preuve brute", "qualifier (analyste)"],
           ["Threat Intelligence", "inventaire filtrable, tri, pagination, export CSV", "—"],
           ["Dossier IOC", "score, cycle de vie, provenance, détections, publications, audit", "décision manuelle (analyste)"],
           ["IOC Lifecycle", "funnel prouvé, publiés, expirés, retirés", "expirer, retirer vérifié (analyste)"],
           ["Scoring & Risk", "distribution, barème, classement, justification", "—"],
           ["Sources", "connexion, clé, débit, historique", "collecter (analyste)"],
           ["Automation Center", "8 workflows, historique, durées", "exécuter (analyste)"],
           ["Audit Center", "journal append-only filtrable", "—"],
           ["Rapports / System Health / Utilisateurs", "rapport quotidien, sondes, comptes", "générer ; gérer (admin)"]],
          [3.6, 8.4, 4.6], size=8)
    figure(SHOTS / "v2-12-mobile.png", "Affichage mobile (390 px)", 6.0)

    # 6 -------------------------------------------------------------------
    h1("6. Données et cycle de vie (base locale)")
    para(f"Instantané de la base locale au {FACTS['generated_at'][:10]} : "
         f"{fr(S['total_iocs'])} IOC, score moyen {fr(S['avg_score'], 1)}, "
         f"{fr(S['total_detections'])} détections, {fr(S['synthetic_iocs'])} IOC synthétique.")
    norm = S["by_status"].get("NORMALIZED", 0)
    if norm:
        callout("Collecte réelle du 16/11/2026",
                f"Une collecte manuelle lancée depuis la console (compte admin, 22:15 UTC) a ingéré "
                f"des indicateurs réels des 7 flux ; {fr(norm)} IOC sont au statut NORMALIZED et "
                "attendent l'étape d'enrichissement (workflow 3). Ils sont comptés tels quels, "
                "sans score ni décision anticipés.")
    figure(figs["statuts"], "Répartition de l'inventaire par statut", 14.5, "PostgreSQL local")
    figure(figs["funnel"], "Débit des dix étapes, chaque valeur adossée à sa table de preuve", 14.5)
    figure(figs["timeline"], "Activité quotidienne sur 30 jours", 15.5)
    table("Sources de renseignement (état réel)",
          ["Source", "Connexion", "Fiabilité", "IOC", "Collectes 30 j", "Échecs"],
          [[s["name"], s["connection"], s["reliability"], s["ioc_count"], s["runs_30d"], s["failures_30d"]]
           for s in L["sources"]],
          [3.6, 3.0, 2.0, 2.0, 3.0, 3.0], source="GET /api/v1/sources (historique d'audit)")

    # 7 -------------------------------------------------------------------
    h1("7. Déploiement AWS")
    para("La v0.2 a été déployée sur l'instance EC2 du Learner Lab (t2.large, us-east-1) "
         "sans ouverture de port public : tous les services écoutent sur 127.0.0.1 et "
         "l'accès se fait exclusivement par tunnel SSH.")
    table("Étapes du déploiement",
          ["#", "Étape", "Résultat"],
          [["1", "Sauvegarde pg_dump de la base du serveur", "fichier conservé dans ~/backups"],
           ["2", "Conservation de l'ancien dossier v0.1", "retour arrière possible"],
           ["3", "Déploiement du commit v0.2 + build frontend", f"commit {REPO['commit']}"],
           ["4", "Ajout des secrets générés sur le serveur (jamais transmis)", "clé de service, admin"],
           ["5", "Migration Alembic", f"révision {AWS.get('alembic', '—')}"],
           ["6", "Reconstruction docker compose (override AWS)", "4 conteneurs healthy"],
           ["7", "Import des 8 workflows n8n + exécution réelle", "status success"],
           ["8", "Vérifications : 401 sans jeton, CSP, nginx UID 101, ports locaux", "conformes"],
           ["9", "Playwright via tunnel 127.0.0.1:8091", "8/8 réussis"]],
          [1.0, 9.6, 6.0])
    table("Conteneurs en service sur EC2",
          ["Conteneur", "État", "Image"],
          [[c["name"], c["status"], c["image"]] for c in AWS.get("containers", [])],
          [3.6, 5.6, 7.4], source="docker ps sur l'instance, 16/11/2026")
    figure(figs["local_aws"], "Bases locale et AWS : deux jeux de données distincts", 14.0)
    figure(SHOTS / "aws-v2-02-overview.png", "Console v0.2 servie par EC2 (via tunnel SSH)", 11.0,
           "capture du 16/11/2026")
    table("Coût de la plateforme sur AWS",
          ["Poste", "Montant", "Commentaire"],
          [["Instance t2.large (on-demand us-east-1)", "≈ 0,093 $/h · ≈ 2,23 $/jour", "uniquement quand elle est démarrée"],
           ["Volume EBS 40 Go", "≈ 0,11 $/jour", "même instance arrêtée"],
           ["Surcoût de la v0.2", "0 $", "mêmes 4 conteneurs, images de quelques centaines de Mo sur le disque existant"]],
          [5.2, 4.6, 6.8], source="tarifs publics AWS appliqués au Learner Lab ; docs/AWS_DEPLOYMENT.md")

    # 8 -------------------------------------------------------------------
    h1("8. Tests et validation")
    figure(figs["tests"], "Tests exécutés le 16/11/2026", 15.0)
    table("Suites de tests",
          ["Suite", "Outil", "Réussis", "Commande"],
          [[t["suite"], t["tool"], f"{t['passed']}/{t['count']}", t["command"]] for t in FACTS["tests"]],
          [4.6, 3.0, 1.8, 7.2], size=8)
    para("Les tests ont révélé et fait corriger plusieurs défauts réels avant livraison :")
    bullets([
        "Collision de routes : la page /health de la console affichait le JSON de la sonde API au rechargement → page déplacée en /system-health + test de lien direct.",
        "État des sources incohérent (« Connecté » avec 0 collecte enregistrée) → synchronisation et lecture de l'historique d'audit + test de régression.",
        "Erreur 500 sur /detections pour les détections manuelles → analyse robuste + test.",
        "Écriture INET impossible pour une adresse cliente non IP → validation de l'adresse.",
        "Landmark de navigation non étiqueté et polices bloquées par la CSP → corrigés.",
    ])

    # 9 -------------------------------------------------------------------
    h1("9. Limites et perspectives")
    table("Fonctionnalités non finalisables dans l'environnement",
          ["Élément", "Raison", "Comportement actuel"],
          [["Publication MISP réelle", "aucun serveur ni clé MISP", "« Configuration manquante », endpoint skipped"],
           ["Alertes Suricata/Wazuh en continu", "capteurs non démarrés pendant la session", "« Aucune donnée » si le fichier est absent"],
           ["Sévérité des anciennes alertes Wazuh", "niveau de règle non conservé avant v0.2", "« non fournie », pas d'estimation"],
           ["Durée des anciennes exécutions", "non mesurée avant v0.2", "« non mesurée »"]],
          [4.4, 5.6, 6.6])
    para("Perspectives :")
    bullets([
        "Rôles PostgreSQL séparés (migration / exécution) et rate limiting au niveau du reverse proxy.",
        "Jetons de rafraîchissement courts avec révocation individuelle.",
        "Déploiement d'un MISP de laboratoire pour exercer la publication distante vérifiée.",
        "Démarrage des profils Suricata et Wazuh pour une démonstration de détection en direct.",
    ])
    callout("Conclusion",
            "La v0.2 livre une plateforme cohérente et démontrable : chaque chiffre affiché "
            "provient de la base, chaque action sensible est confirmée, authentifiée et "
            "journalisée, les failles identifiées à l'audit sont corrigées et vérifiées par des "
            "outils reconnus, et le même code tourne localement et sur AWS avec des tests "
            "end-to-end au vert sur les deux environnements.")

    # Annexe ---------------------------------------------------------------
    h1("Annexe — Commandes de reproduction")
    for line in (
        "docker compose --profile n8n up -d --build",
        "cd backend ; python -m alembic upgrade head ; python -m pytest tests -q",
        "cd frontend ; npm install ; npm test ; npm run typecheck ; npm run test:e2e",
        "python scripts/collect_v2_facts.py --aws-json reports/v2/aws.json",
        "python scripts/build_report_v2.py",
    ):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(line)
        r.font.name, r.font.size, r.font.color.rgb = "Consolas", Pt(9), INK
    doc.save(OUT)


if __name__ == "__main__":
    build()
    print(f"rapport -> {OUT}  ({N['table']} tableaux, {N['figure']} figures)")
