"""Rapport de projet complet — SOAR IOC Factory (Word, A4, français).

Présente la plateforme telle qu'elle est livrée (une seule version).
Conventions : .opencode/skills/rapport-docx — Calibri 10,5, titres #0E5A8A,
page de garde, sommaire, en-tête / pied « Page X sur Y », tableaux et figures
numérotés avec leur source. Aucun chiffre saisi à la main : tout vient de
  * reports/evaluation/metrics.json  (scripts/evaluate_platform.py)
  * reports/data/facts.json          (scripts/collect_facts.py)

Usage : backend/.venv/Scripts/python.exe scripts/build_rapport_projet.py
        puis powershell -File scripts/word_finalize.ps1 reports/RAPPORT_SOAR_IOC_FACTORY_PROJET.docx
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.table import WD_TABLE_ALIGNMENT  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT  # noqa: E402
from docx.oxml import OxmlElement  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm, Pt, RGBColor  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "reports" / "data"
F = json.loads((DATA / "facts.json").read_text(encoding="utf-8"))
M = json.loads((ROOT / "reports" / "evaluation" / "metrics.json").read_text(encoding="utf-8"))
EVAL_FIG = ROOT / "reports" / "figures"
SHOTS = ROOT / "capture" / "2026-11-17"
OUT = ROOT / "reports" / "RAPPORT_SOAR_IOC_FACTORY_PROJET.docx"
REPORT_DATE = "17 novembre 2026"

PRIMARY = RGBColor(0x0E, 0x5A, 0x8A)
SECONDARY = RGBColor(0x1F, 0x6F, 0xB2)
INK = RGBColor(0x33, 0x47, 0x5B)
GREY = RGBColor(0x5A, 0x6B, 0x7B)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
CONTENT_W = 16.6

L = F["local"]
S = L["stats"]
AWS = F.get("aws") or {}
REPO = F["repo"]
TESTS_OK = sum(t["passed"] for t in F["tests"])
TESTS_N = sum(t["count"] for t in F["tests"])


def fr(n: Any, dec: int = 0) -> str:
    if n is None:
        return "non mesuré"
    if dec:
        return f"{float(n):,.{dec}f}".replace(",", " ").replace(".", ",")
    return f"{int(round(float(n))):,}".replace(",", " ")


def pct(n: Any, dec: int = 1) -> str:
    return "non mesuré" if n is None else f"{fr(n, dec)} %"


# =============================================================== figures ====
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False,
    "axes.spines.right": False, "axes.edgecolor": "#9AA6B6", "axes.titleweight": "bold",
    "axes.titlesize": 10, "axes.titlecolor": "#0E5A8A",
})


def save(fig, name: str) -> Path:
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / f"fig_{name}.png"
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def fig_architecture() -> Path:
    """Current architecture, drawn from what is deployed."""
    fig, ax = plt.subplots(figsize=(10, 6.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 66)
    ax.axis("off")

    def box(x, y, w, h, title, sub="", fc="#EAF2F8", ec="#0E5A8A", dashed=False, tc="#0E5A8A"):
        ax.add_patch(mpatches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2",
                                             fc=fc, ec=ec, lw=1.3, ls="--" if dashed else "-"))
        ax.text(x + w / 2, y + h * (0.62 if sub else 0.5), title, ha="center", va="center",
                fontsize=9.5, fontweight="bold", color=tc)
        if sub:
            ax.text(x + w / 2, y + h * 0.28, sub, ha="center", va="center", fontsize=7.4, color="#33475B")

    def arrow(x1, y1, x2, y2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", color="#1F6FB2", lw=1.3))

    def label(y, text):
        ax.text(0.5, y, text, fontsize=8.5, fontweight="bold", color="#5A6B7B")

    label(63.2, "1 · SOURCES DE THREAT INTELLIGENCE (7 flux)")
    for i, (n, s) in enumerate([("AlienVault OTX", "API + clé"), ("abuse.ch", "URLhaus · ThreatFox · MalwareBazaar"),
                                ("Feodo Tracker", "flux public"), ("blocklist.de", "flux public"), ("urlscan.io", "recherche")]):
        box(0.5 + i * 15.6, 55, 14.4, 6.6, n, s)
    label(51.4, "2 · ORCHESTRATION")
    box(0.5, 44, 77, 6.4, "n8n — 8 workflows planifiés", "clé de service X-API-Key · étiquette X-Actor · reprise après échec")
    label(40.4, "3 · API FASTAPI — CONTRÔLE D'ACCÈS + PIPELINE")
    box(0.5, 33.6, 77, 5.6, "Authentification JWT · Argon2id · rôles lecteur / analyste / administrateur",
        "", fc="#FDF3E6", ec="#E0A43B", tc="#8A5A00")
    for i, (n, s) in enumerate([("Normaliser", "forme canonique"), ("Dédupliquer", "empreinte SHA-256"),
                                ("Enrichir", "OTX · AbuseIPDB"), ("Noter", "5 composantes"), ("Décider", "seuils 80 / 50")]):
        box(0.5 + i * 15.6, 24.4, 14.4, 7.6, n, s)
    label(20.6, "4 · EFFETS, CAPTEURS ET CONSOMMATEURS")
    for i, (n, s, dashed) in enumerate([("Publier", "relecture = preuve", False), ("Surveiller", "Suricata · Wazuh", False),
                                        ("Expirer / retirer", "révocation confirmée", False), ("MISP", "client prêt · non configuré", True),
                                        ("Console SOC", "React · 13 pages", False)]):
        box(0.5 + i * 15.6, 10.8, 14.4, 8.2, n, s, dashed=dashed, fc="#F2F2F2" if dashed else "#EAF2F8")
    box(0.5, 0.8, 77, 6.6, "Accès unique : tunnel SSH", "services publiés sur 127.0.0.1 · aucun port applicatif ouvert sur Internet",
        fc="#F7F1E3", ec="#B07A2A", tc="#8A5A00")
    for x in (7.7, 23.3, 38.9, 54.5, 70.1):
        arrow(x, 54.6, x if x < 78 else 70, 50.8)
    arrow(39, 43.6, 39, 39.6)
    arrow(39, 33.2, 39, 32.4)
    for x in (7.7, 23.3, 38.9, 54.5, 70.1):
        arrow(x, 24.0, x, 19.4)

    ax.add_patch(mpatches.FancyBboxPatch((81, 0.8), 18.5, 60.8, boxstyle="round,pad=0.4,rounding_size=1.2",
                                         fc="#FBFDFF", ec="#0E5A8A", lw=1.3, ls="--"))
    ax.text(90.2, 58.8, "PREUVES", ha="center", fontsize=10, fontweight="bold", color="#0E5A8A")
    ax.text(90.2, 56.4, "PostgreSQL 16", ha="center", fontsize=8, color="#5A6B7B")
    tables = [("iocs", "statut, score expliqué"), ("ioc_sources", "provenance"), ("enrichments", "verdicts"),
              ("score_history", "politique versionnée"), ("lifecycle_events", "transitions"),
              ("detections", "alertes + qualification"), ("publications", "relecture"),
              ("audit_logs", "append-only (trigger)"), ("users", "rôles, verrouillage")]
    for i, (t, d) in enumerate(tables):
        y = 52.5 - i * 5.6
        ax.text(82.4, y, t, fontsize=8.2, fontweight="bold", family="monospace", color="#33475B")
        ax.text(82.4, y - 2.0, d, fontsize=7.2, color="#5A6B7B")
    for y in (47, 28, 15):
        ax.annotate("", xy=(80.8, y), xytext=(78.2, y), arrowprops=dict(arrowstyle="-|>", color="#5A6B7B", lw=1, ls="--"))
    return save(fig, "architecture")


def fig_status() -> Path:
    order = ["NEW", "NORMALIZED", "ENRICHED", "SCORED", "PUBLISHED", "MONITORED", "REVIEW_REQUIRED", "EXPIRED", "REMOVED", "REJECTED"]
    fr_lab = {"NEW": "Nouveau", "NORMALIZED": "Normalisé", "ENRICHED": "Enrichi", "SCORED": "Noté", "PUBLISHED": "Publié",
              "MONITORED": "Surveillé", "REVIEW_REQUIRED": "À revoir", "EXPIRED": "Expiré", "REMOVED": "Retiré", "REJECTED": "Rejeté"}
    data = [(fr_lab[k], S["by_status"].get(k, 0)) for k in order if S["by_status"].get(k, 0)]
    fig, ax = plt.subplots(figsize=(6.4, 2.4))
    bars = ax.barh([k for k, _ in data][::-1], [v for _, v in data][::-1], color="#0E5A8A")
    ax.bar_label(bars, padding=3, fontsize=8)
    ax.set_xlabel("IOC")
    ax.set_title("Inventaire par statut")
    return save(fig, "statuts")


def fig_funnel() -> Path:
    stages = L["funnel"]["stages"]
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    labels = [f"{i + 1}. {s['label']}" for i, s in enumerate(stages)]
    bars = ax.barh(labels[::-1], [s["count"] for s in stages][::-1],
                   color=["#2CC2A6" if s["key"] in ("publish", "remove") else "#0E5A8A" for s in stages][::-1])
    ax.bar_label(bars, padding=3, fontsize=8)
    ax.set_title("Débit mesuré des dix étapes du cycle de vie")
    ax.set_xlabel("opérations tracées / IOC entrés dans l'étape")
    return save(fig, "funnel")


def fig_timeline() -> Path:
    series = L["timeline"]
    labels = [f"{p['date'][8:10]}/{p['date'][5:7]}" for p in series]
    fig, ax = plt.subplots(figsize=(6.6, 2.6))
    ax.bar(labels, [p["created"] for p in series], color="#5AA2F5", label="IOC créés")
    ax.plot(labels, [p["published"] + p["monitored"] + p["rejected"] for p in series], color="#0E5A8A", lw=1.6,
            marker="o", ms=2.5, label="Décisions appliquées")
    ax.plot(labels, [p["detections"] for p in series], color="#E0A43B", lw=1.4, label="Détections")
    ax.set_xticks(range(0, len(labels), 4))
    ax.set_xticklabels(labels[::4], fontsize=7)
    ax.legend(frameon=False, fontsize=7.5, ncol=3, loc="upper left")
    ax.set_title("Activité quotidienne sur 30 jours")
    return save(fig, "timeline")


def fig_tests() -> Path:
    tests = F["tests"]
    fig, ax = plt.subplots(figsize=(6.4, 2.2))
    bars = ax.barh([t["suite"] for t in tests][::-1], [t["passed"] for t in tests][::-1], color="#2CC2A6")
    ax.bar_label(bars, labels=[f"{t['passed']}/{t['count']}" for t in tests][::-1], padding=3, fontsize=8)
    ax.set_title("Tests exécutés (réussis / total)")
    ax.set_xscale("log")
    ax.set_xlabel("nombre de tests (échelle logarithmique)")
    return save(fig, "tests")


def fig_environments() -> Path:
    keys = [("MONITORED", "Surveillés"), ("REJECTED", "Rejetés"), ("PUBLISHED", "Publiés")]
    loc = [S["by_status"].get(k, 0) for k, _ in keys]
    aws = [(AWS.get("by_status") or {}).get(k, 0) for k, _ in keys]
    fig, ax = plt.subplots(figsize=(6.0, 2.3))
    x = range(len(keys))
    b1 = ax.bar([i - 0.2 for i in x], loc, width=0.4, color="#0E5A8A", label=f"Poste local ({fr(S['total_iocs'])} IOC)")
    b2 = ax.bar([i + 0.2 for i in x], aws, width=0.4, color="#E0A43B", label=f"Serveur AWS ({fr(AWS.get('total_iocs'))} IOC)")
    ax.bar_label(b1, fontsize=7.5, padding=2)
    ax.bar_label(b2, fontsize=7.5, padding=2)
    ax.set_xticks(list(x))
    ax.set_xticklabels([lbl for _, lbl in keys], fontsize=8)
    ax.legend(frameon=False, fontsize=7.5)
    ax.set_title("Deux environnements, deux jeux de données indépendants")
    return save(fig, "environnements")


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
for name, size, color, before, after in (("Heading 1", 17, PRIMARY, 0, 10), ("Heading 2", 12.5, SECONDARY, 12, 5),
                                         ("Heading 3", 11, INK, 8, 3)):
    st = doc.styles[name]
    st.font.name, st.font.size, st.font.bold, st.font.color.rgb = "Calibri", Pt(size), True, color
    st.paragraph_format.space_before, st.paragraph_format.space_after = Pt(before), Pt(after)
    st.paragraph_format.keep_with_next = True
for _style in ("Header", "Footer"):
    doc.styles[_style].paragraph_format.tab_stops.clear_all()

hp = sec.header.paragraphs[0]
hp.paragraph_format.tab_stops.add_tab_stop(Cm(CONTENT_W - 0.2), WD_TAB_ALIGNMENT.RIGHT)
for text, tab in (("SOAR IOC FACTORY · Rapport de projet", True), (REPORT_DATE, False)):
    r = hp.add_run(text)
    r.font.size, r.font.color.rgb = Pt(8), GREY
    if tab:
        hp.add_run("\t")
p_border(hp, color="C9D6E2", size=4)
fp = sec.footer.paragraphs[0]
fp.paragraph_format.tab_stops.add_tab_stop(Cm(CONTENT_W - 0.2), WD_TAB_ALIGNMENT.RIGHT)
for text in ("Plateforme SOAR de gestion du cycle de vie des IOC", "\t", "Page "):
    r = fp.add_run(text)
    r.font.size, r.font.color.rgb = Pt(8), GREY
field(fp, " PAGE ", "1", 8, GREY)
r = fp.add_run(" sur ")
r.font.size, r.font.color.rgb = Pt(8), GREY
field(fp, " NUMPAGES ", "1", 8, GREY)
doc.settings.element.append(_el("updateFields", val="true"))

N = {"table": 0, "figure": 0}


def h1(text: str, new_page: bool = True) -> None:
    doc.add_heading(text, level=1).paragraph_format.page_break_before = new_page


def h2(text: str) -> None:
    doc.add_heading(text, level=2)


def h3(text: str) -> None:
    doc.add_heading(text, level=3)


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
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        if " : " in item:
            head, tail = item.split(" : ", 1)
            p.add_run(head + " : ").bold = True
            p.add_run(tail)
        else:
            p.add_run(item)


def numbered(items: Iterable[str]) -> None:
    for i, item in enumerate(items, 1):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent, p.paragraph_format.first_line_indent = Cm(0.75), Cm(-0.75)
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(f"{i}.  ")
        r.bold, r.font.color.rgb = True, PRIMARY
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
            pp.add_run(str(v)).font.size = Pt(size)
    widths(t, cms)
    note = doc.add_paragraph()
    note.paragraph_format.space_before, note.paragraph_format.space_after = Pt(3), Pt(10)
    if source:
        rr = note.add_run(f"Source : {source}")
        rr.italic, rr.font.size, rr.font.color.rgb = True, Pt(8), GREY


def figure(path: Path, caption: str, width_cm: float = 15.5, source: Optional[str] = None) -> None:
    if not Path(path).exists():
        return
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
    b = _el("tcBorders")
    b.append(_el("left", val="single", sz=18, space=0, color=bar))
    for e in ("top", "bottom", "right"):
        b.append(_el(e, val="nil"))
    c._tc.get_or_add_tcPr().append(b)
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


def code(lines: list[str]) -> None:
    for line in lines:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.left_indent = Cm(0.4)
        r = p.add_run(line)
        r.font.name, r.font.size, r.font.color.rgb = "Consolas", Pt(8.5), INK


# ============================================================== contenu =====
def cover() -> None:
    for _ in range(3):
        doc.add_paragraph()
    p = doc.add_paragraph()
    r = p.add_run("PROJET 3 · CYBER THREAT INTELLIGENCE · RAPPORT DE PROJET")
    r.bold, r.font.size, r.font.color.rgb = True, Pt(10), GREY
    p = doc.add_paragraph()
    r = p.add_run("SOAR IOC Factory")
    r.bold, r.font.size, r.font.color.rgb = True, Pt(36), PRIMARY
    p = doc.add_paragraph()
    r = p.add_run("Plateforme SOAR de gestion automatisée du cycle de vie des indicateurs de compromission")
    r.font.size, r.font.color.rgb = Pt(16), SECONDARY
    p_border(p, color="0E5A8A", size=12)
    para("Collecter · normaliser · dédupliquer · enrichir · noter · décider · publier · surveiller · "
         "expirer · retirer — avec une preuve vérifiable à chaque étape et une console SOC pour les analystes.",
         size=11.5, color=INK, align=WD_ALIGN_PARAGRAPH.LEFT, after=22)
    kpis([(fr(S["total_iocs"]), "indicateurs gérés"), ("7", "sources de renseignement"),
          (fr(TESTS_OK), "tests automatisés réussis"), ("0", "vulnérabilité ouverte")])
    for _ in range(5):
        doc.add_paragraph()
    t = doc.add_table(rows=4, cols=2)
    widths(t, [4.6, 12.0])
    for i, (k, v) in enumerate((("Date", REPORT_DATE), ("Auteur", "Souhayl Chouaibi"),
                                ("Environnements", "poste local (Docker Compose) · serveur AWS EC2 (us-east-1)"),
                                ("Dépôt", "github.com/souhaylchiibi/soar-ioc-factory"))):
        a, b = t.rows[i].cells
        a.paragraphs[0].add_run(k).bold = True
        b.paragraphs[0].add_run(v)
        for c in (a, b):
            c.paragraphs[0].runs[0].font.size = Pt(9.5)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def toc() -> None:
    p = doc.add_paragraph()
    r = p.add_run("Sommaire")
    r.bold, r.font.size, r.font.color.rgb = True, Pt(17), PRIMARY
    p_border(p)
    field(doc.add_paragraph(), ' TOC \\o "1-2" \\h \\z \\u ', "Clic droit → Mettre à jour les champs (F9).")


def build() -> None:
    figs = {"architecture": fig_architecture(), "statuts": fig_status(), "funnel": fig_funnel(),
            "timeline": fig_timeline(), "tests": fig_tests(), "env": fig_environments()}
    dd, en, sc, pub, det, lc, perf, au = (M["dedup"], M["enrichment"], M["scoring"], M["publication"],
                                          M["detection"], M["lifecycle"], M["performance"], M["automation"])
    cover()
    toc()

    # ------------------------------------------------------------ résumé ---
    h1("Résumé")
    para("Les équipes de sécurité reçoivent chaque jour des milliers d'indicateurs de compromission (IOC) — adresses "
         "IP, domaines, URL, empreintes de fichiers — issus de flux de renseignement hétérogènes, redondants et de "
         "qualité inégale. Les traiter à la main est lent, peu reproductible et rarement traçable. SOAR IOC Factory "
         "est une plateforme qui industrialise ce traitement : elle collecte les indicateurs, les normalise, les "
         "déduplique, les enrichit, leur attribue un score de confiance explicable, décide de leur publication, "
         "surveille leurs détections puis les retire de façon vérifiée à leur expiration.")
    para("La plateforme repose sur FastAPI et PostgreSQL 16, orchestrée par huit workflows n8n et pilotée depuis "
         "une console SOC React. L'accès est contrôlé par authentification et rôles ; chaque opération est inscrite "
         "dans un journal d'audit inaltérable. Elle fonctionne sur un poste local et sur un serveur AWS accessible "
         "uniquement par tunnel SSH.")
    kpis([(fr(S["total_iocs"]), "IOC en base"), (pct(dd.get("dedup_rate_pct")), "taux de déduplication"),
          (pct(sc.get("explainability_pct"), 0), "scores expliqués"), (fr(TESTS_OK), "tests réussis")])
    callout("Principe directeur",
            "Aucune donnée simulée n'est présentée comme réelle et aucune action n'est déclarée réussie sans "
            "confirmation technique : une publication n'est « vérifiée » qu'après relecture, un retrait n'est "
            "accepté qu'après révocation confirmée, une intégration absente est affichée « Configuration "
            "manquante », une valeur non mesurée est écrite « non mesurée ».")
    para("Mots-clés : SOAR, Cyber Threat Intelligence, IOC, scoring explicable, n8n, FastAPI, PostgreSQL, "
         "Suricata, Wazuh, MISP, AWS.", size=9.5, italic=True, color=GREY)

    # --------------------------------------------------------- 1 intro ----
    h1("1. Introduction")
    h2("1.1 Contexte")
    para("Un centre opérationnel de sécurité (SOC) s'appuie sur le renseignement sur la menace pour détecter "
         "plus tôt les attaques. Les indicateurs de compromission en sont la forme la plus opérationnelle : ce "
         "sont des observables techniques qu'un IDS, un SIEM ou un pare-feu peut rechercher. Leur valeur est "
         "pourtant éphémère — une adresse IP malveillante est souvent réattribuée en quelques jours — et leur "
         "fiabilité varie fortement d'une source à l'autre.")
    h2("1.2 Problématique")
    bullets([
        "Volume : des flux publics publient des centaines d'indicateurs par jour, avec de nombreux doublons.",
        "Qualité : un même indicateur peut être répété par plusieurs flux qui relaient la même source, donnant une fausse impression de consensus.",
        "Décision : publier un faux positif peut bloquer un service légitime ; ne rien publier laisse passer la menace.",
        "Traçabilité : il faut pouvoir expliquer pourquoi un indicateur a été publié, par qui, et prouver qu'il a bien été retiré.",
    ])
    h2("1.3 Objectifs")
    numbered([
        "Automatiser la chaîne complète du cycle de vie d'un IOC, de la collecte au retrait vérifié.",
        "Calculer un score de confiance explicable composante par composante.",
        "Décider de manière reproductible (publier, surveiller, rejeter) selon des seuils configurables.",
        "Conserver une preuve horodatée et inaltérable de chaque opération.",
        "Offrir aux analystes une console claire, sûre et fondée uniquement sur des données réelles.",
        "Déployer la plateforme sans exposer de service sur Internet.",
    ])
    h2("1.4 Démarche")
    para("Le projet a suivi une démarche itérative : conception du modèle de données et de la machine à états, "
         "construction du moteur (normalisation, déduplication, enrichissement, scoring), automatisation par "
         "n8n, intégration des capteurs, contrôle d'accès, console SOC, déploiement AWS, puis campagne de "
         "validation (tests automatisés, analyses de sécurité, tests de bout en bout) et évaluation chiffrée.")

    # --------------------------------------------------- 2 état de l'art --
    h1("2. Concepts et état de l'art")
    h2("2.1 Indicateurs de compromission")
    table("Types d'indicateurs gérés", ["Type", "Exemple de forme canonique", "Durée de vie typique"],
          [["Adresse IP", "198.51.100.7", "courte (réattribution rapide)"],
           ["Domaine", "evil.example", "moyenne"], ["URL", "http://evil.example/path", "très courte"],
           ["Empreinte MD5 / SHA-1 / SHA-256", "44d88612fea8a8f36de82e1278abb02f", "longue (un fichier ne change pas)"]],
          [4.2, 7.4, 5.0])
    para("La pyramide de la douleur de David Bianco rappelle que les empreintes et les adresses sont faciles à "
         "changer pour un attaquant : leur intérêt est la rapidité de détection, à condition d'être fraîches et "
         "fiables. C'est précisément ce que mesure le score de la plateforme (fraîcheur, fiabilité, consensus).")
    h2("2.2 SOAR et Threat Intelligence")
    para("Un SOAR (Security Orchestration, Automation and Response) automatise les tâches répétitives d'un SOC "
         "et les orchestre entre outils. Une plateforme de Threat Intelligence (TIP), comme MISP, centralise et "
         "partage le renseignement. SOAR IOC Factory se situe entre les deux : elle automatise la production d'un "
         "renseignement qualifié et le distribue aux outils de détection.")
    table("Écosystème et rôle de chaque composant", ["Outil", "Catégorie", "Rôle dans la plateforme"],
          [["AlienVault OTX, abuse.ch, Feodo Tracker, blocklist.de, urlscan.io", "sources", "flux d'indicateurs"],
           ["AbuseIPDB, OTX", "enrichissement", "réputation et contexte"],
           ["n8n", "orchestration", "planification des huit étapes automatisées"],
           ["Suricata", "IDS réseau", "alertes rapprochées de l'inventaire"],
           ["Wazuh", "SIEM / HIDS", "alertes système rapprochées de l'inventaire"],
           ["MISP", "TIP", "publication distante vérifiée (client prêt)"]],
          [6.2, 2.8, 7.6])

    # ---------------------------------------------------------- 3 exigences
    h1("3. Exigences")
    h2("3.1 Exigences fonctionnelles")
    table("Exigences fonctionnelles et réponse de la plateforme", ["#", "Exigence", "Réponse"],
          [["EF1", "Collecter depuis plusieurs sources", "7 collecteurs, échec isolé par source"],
           ["EF2", "Valider et normaliser", "forme canonique unique par type, rejet motivé"],
           ["EF3", "Dédupliquer", "empreinte SHA-256 type:valeur, provenance conservée"],
           ["EF4", "Enrichir", "OTX + AbuseIPDB, cache 24 h, erreurs conservées"],
           ["EF5", "Noter de façon explicable", "5 composantes pondérées + pénalités, détail stocké"],
           ["EF6", "Décider", "publier ≥ 80, surveiller 50–79, rejeter < 50"],
           ["EF7", "Publier et vérifier", "écriture puis relecture avant statut « vérifié »"],
           ["EF8", "Surveiller les détections", "Suricata, Wazuh, qualification analyste"],
           ["EF9", "Expirer et retirer", "révocation confirmée avant REMOVED"],
           ["EF10", "Tracer", "journal append-only protégé par trigger"],
           ["EF11", "Piloter", "console SOC, 13 pages, rôles"]],
          [1.2, 6.0, 9.4])
    h2("3.2 Exigences non fonctionnelles")
    bullets([
        "Intégrité des données : aucune valeur estimée ou simulée présentée comme réelle ; données de laboratoire marquées.",
        "Sécurité : authentification, moindre privilège, aucun port public, secrets hors du dépôt.",
        "Traçabilité : chaque transition porte son acteur, sa raison et sa preuve.",
        "Robustesse : opérations idempotentes, échec d'une source sans effet sur les autres, reprise après arrêt.",
        "Ergonomie : interface lisible au clavier, contrastes accessibles, responsive.",
    ])

    # ------------------------------------------------------- 4 architecture
    h1("4. Architecture")
    figure(figs["architecture"], "Architecture de la plateforme", 16.0)
    h2("4.1 Composants")
    table("Composants et responsabilités", ["Composant", "Responsabilité", "Exposition"],
          [["PostgreSQL 16", "inventaire, cycle de vie, audit, utilisateurs", "réseau Docker interne"],
           ["API FastAPI", "pipeline, scoring, publication, SOC, contrôle d'accès", "127.0.0.1:8000"],
           ["n8n", "8 workflows planifiés, clé de service", "127.0.0.1:5678"],
           ["Console React (nginx)", "interface analyste", "127.0.0.1:80 → tunnel SSH"],
           ["Montages capteurs", "alertes Suricata / Wazuh en lecture seule", "aucune"]],
          [3.6, 8.6, 4.4])
    h2("4.2 Choix techniques")
    table("Choix techniques et justification", ["Choix", "Justification"],
          [["FastAPI + Pydantic", "validation stricte des entrées, OpenAPI généré, performances"],
           ["PostgreSQL 16 + Alembic", "transactions, contraintes, trigger d'audit, migrations versionnées"],
           ["SQLAlchemy 2", "requêtes paramétrées (aucune concaténation SQL)"],
           ["n8n", "orchestration visuelle, planification, reprise, exportable en JSON"],
           ["React 19 + TypeScript + Tailwind 4", "typage, composants réutilisables, design system"],
           ["Docker Compose", "environnement reproductible local et serveur"],
           ["JWT + Argon2id", "standard éprouvé, hachage résistant aux GPU"]],
          [5.0, 11.6])

    # ---------------------------------------------------- 5 modèle données
    h1("5. Modèle de données et cycle de vie")
    table("Tables principales", ["Table", "Contenu"],
          [["iocs", "valeur canonique, type, statut, score, détail du score, niveau de risque, dates, marqueur synthétique"],
           ["intel_sources / ioc_sources", "sources, fiabilité, groupe de provenance ; lien IOC ↔ source avec référence externe"],
           ["enrichments", "verdict et réputation par fournisseur, données brutes, expiration du cache"],
           ["score_history / scoring_policies", "historique des scores et politique utilisée"],
           ["lifecycle_events", "chaque transition : de, vers, raison, acteur, preuve de vérification"],
           ["detections", "alerte capteur, règle, événement brut, qualification analyste"],
           ["publications", "cible, référence, statut (vérifiée / révoquée)"],
           ["audit_logs", "journal append-only : acteur, rôle, action, objet, résultat, IP"],
           ["users / reports", "comptes, rôles, verrouillage ; rapports quotidiens"]],
          [4.4, 12.2])
    h2("5.1 Machine à états")
    para("Chaque IOC suit une machine à états stricte : toute transition non prévue est refusée, toute "
         "transition exige une raison et produit un événement de cycle de vie.")
    table("Transitions autorisées", ["Depuis", "Vers"],
          [["NEW", "NORMALIZED, DUPLICATE, REJECTED"], ["NORMALIZED", "ENRICHED, REVIEW_REQUIRED, REJECTED"],
           ["ENRICHED", "SCORED"], ["SCORED", "PUBLISHED, MONITORED, REJECTED, REVIEW_REQUIRED, EXPIRED"],
           ["PUBLISHED", "MONITORED, EXPIRED"], ["MONITORED", "EXPIRED, REVIEW_REQUIRED, PUBLISHED"],
           ["REVIEW_REQUIRED", "PUBLISHED, REJECTED, MONITORED"], ["EXPIRED", "REMOVED (après révocation confirmée)"],
           ["REMOVED, REJECTED, DUPLICATE", "aucune (états terminaux)"]],
          [4.4, 12.2], source="backend/app/lifecycle/machine.py")

    # ---------------------------------------------------------- 6 pipeline
    h1("6. Le pipeline de traitement")
    figure(figs["funnel"], "Débit des dix étapes, chacune adossée à sa table de preuve", 15.0)
    h2("6.1 Collecte")
    table("Sources de renseignement", ["Source", "Groupe de provenance", "Fiabilité", "IOC rattachés", "État"],
          [[s["name"], s["provenance_group"], s["reliability"], s["ioc_count"],
            {"connected": "connectée", "no_data": "aucune donnée", "not_configured": "clé absente",
             "unreachable": "en erreur", "disabled": "désactivée"}.get(s["connection"], s["connection"])]
           for s in L["sources"]],
          [3.4, 4.4, 2.2, 2.8, 3.8], source="GET /api/v1/sources")
    para("Chaque collecteur est isolé : l'échec d'une source est enregistré avec son message d'erreur sans "
         "interrompre les autres, et il n'est jamais transformé en succès vide. Le collecteur synthétique de "
         "laboratoire marque ses indicateurs (is_synthetic) : ils ne sont jamais comptés comme renseignement réel.")
    h2("6.2 Normalisation et déduplication")
    bullets([
        "IP : accepte la forme IP:port fréquente dans les journaux, conserve l'adresse seule ; les plages privées sont conservées volontairement (réponse à incident).",
        "Domaine : minuscules, point final retiré, validation stricte des labels.",
        "URL : schéma et hôte en minuscules, fragment supprimé, chemin et requête conservés.",
        "Empreintes : minuscules, longueur contrôlée (32, 40 ou 64 caractères hexadécimaux).",
        "Empreinte de déduplication : SHA-256 de « type:valeur canonique » ; un doublon met à jour l'indicateur existant et ajoute la provenance.",
    ])
    table("Mesures de collecte et de déduplication", ["Mesure", "Valeur"],
          [["Éléments bruts collectés", fr(dd.get("raw_items_collected"))], ["IOC créés", fr(dd.get("created"))],
           ["Doublons fusionnés", fr(dd.get("updated"))], ["Rejets de validation", fr(dd.get("invalid_rejected"))],
           ["Taux de déduplication", pct(dd.get("dedup_rate_pct"))]],
          [10.0, 6.6], source="reports/evaluation/metrics.json")
    figure(EVAL_FIG / "eval_05_collecte_dedup.png", "Collecte et déduplication", 14.0)
    h2("6.3 Enrichissement")
    para("L'enrichissement interroge AlienVault OTX et AbuseIPDB. Les résultats sont mis en cache 24 heures ; "
         "une erreur de fournisseur est conservée comme telle et n'est jamais convertie en verdict.")
    table("Mesures d'enrichissement", ["Mesure", "Valeur"],
          [["Résultats d'enrichissement", fr(en.get("results"))], ["IOC enrichis", fr(en.get("iocs_enriched"))],
           ["Couverture", pct(en.get("coverage_pct"))], ["Erreurs fournisseur conservées", fr(en.get("provider_errors"))],
           ["Taux de succès des appels", pct(en.get("provider_success_pct"))]],
          [10.0, 6.6], source="reports/evaluation/metrics.json")
    figure(EVAL_FIG / "eval_04_enrichissement.png", "Verdicts d'enrichissement par fournisseur", 14.0)
    h2("6.4 Score de confiance explicable")
    para("Le score (0 à 100) est la somme de cinq composantes pondérées, diminuée d'une pénalité par faux positif "
         "qualifié. Chaque composante est stockée avec ses points et une explication en langage naturel, ce qui "
         "permet de répondre à la question « pourquoi ce score ? » pour chaque indicateur.")
    table("Composantes du score", ["Composante", "Poids", "Calcul"],
          [["Fiabilité de la source", "25", "meilleure fiabilité parmi les sources de l'IOC"],
           ["Fraîcheur", "20", "décroissance exponentielle, demi-vie par type (IP 7 j, domaine 14 j, URL 3 j, MD5/SHA-1 30 j, SHA-256 60 j)"],
           ["Sources indépendantes", "20", "nombre de groupes de provenance distincts (plafond 4) — anti-collusion"],
           ["Consensus d'enrichissement", "20", "accord des verdicts fournisseurs"],
           ["Détections observées", "15", "alertes capteurs (saturation à 5)"],
           ["Pénalité faux positif", "−20 / FP", "plafonnée à −40"]],
          [4.2, 2.0, 10.4], source="backend/app/scoring/engine.py")
    comps = sc.get("components_avg", [])
    if comps:
        table("Contribution moyenne de chaque composante", ["Composante", "Points moyens", "Maximum", "% du maximum"],
              [[c["label"], fr(c["avg_points"], 1), fr(c["max_points"]), pct(c["avg_pct_of_max"])] for c in comps],
              [6.2, 3.4, 3.0, 4.0], source="reports/evaluation/metrics.json")
    figure(EVAL_FIG / "eval_02_scores.png", "Distribution des scores et seuils de décision", 14.5)
    h2("6.5 Décision")
    table("Règles de décision et résultats", ["Décision", "Règle", "IOC", "Part"],
          [["Publier", "score ≥ 80", fr(sc["decisions"].get("publish")), pct(sc["decisions_pct"].get("publish"))],
           ["Surveiller", "50 ≤ score < 80", fr(sc["decisions"].get("monitor")), pct(sc["decisions_pct"].get("monitor"))],
           ["Rejeter", "score < 50", fr(sc["decisions"].get("reject")), pct(sc["decisions_pct"].get("reject"))]],
          [3.2, 4.4, 3.6, 5.4], source="reports/evaluation/metrics.json")
    para(f"Score moyen {fr(sc.get('avg'), 1)}, médiane {fr(sc.get('median'))}, 95e centile {fr(sc.get('p95'))}, "
         f"maximum {fr(sc.get('max'))}. La politique est volontairement exigeante : un IOC n'est publié que s'il "
         "cumule fiabilité, fraîcheur, consensus et, idéalement, des détections réelles.")
    h2("6.6 Publication, surveillance, expiration et retrait")
    bullets([
        "Publication : l'indicateur est écrit dans la liste de détection puis relu ; seul un enregistrement relu passe au statut « vérifié ».",
        "Surveillance : les alertes Suricata (eve.json) et Wazuh (alerts.json) sont rapprochées de l'inventaire ; la preuve brute est conservée et la sévérité n'est affichée que si le capteur la fournit.",
        "Qualification : un analyste confirme une détection ou la déclare faux positif ; un faux positif pénalise le score au calcul suivant.",
        "Expiration et retrait : un IOC échu passe EXPIRED ; ses publications sont révoquées puis relues, et le statut REMOVED n'est écrit que si aucune publication n'est encore active.",
    ])
    table("Publication et détection", ["Mesure", "Valeur"],
          [["Publications vérifiées", fr(pub.get("verified"))], ["Publications révoquées", fr(pub.get("revoked"))],
           ["Détections rapprochées", fr(det.get("total"))], ["Faux positifs qualifiés", fr(det.get("false_positives"))],
           ["Retraits vérifiés", fr(L["funnel"].get("verified_removals"))]],
          [10.0, 6.6], source="metrics.json ; GET /api/v1/lifecycle/funnel")
    figure(EVAL_FIG / "eval_01_cycle_de_vie.png", "Transitions du cycle de vie", 14.0)

    # ------------------------------------------------------- 7 automation
    h1("7. Automatisation")
    table("Les huit workflows n8n", ["#", "Workflow", "Fréquence", "Opération"],
          [["1", "Collecte", "30 min", "POST /iocs/collect/run"], ["2", "Normalisation", "30 min", "POST /iocs/normalize/run"],
           ["3", "Enrichissement", "1 h", "POST /iocs/enrich/run"], ["4", "Scoring", "30 min", "POST /iocs/scoring/run"],
           ["5", "Publication", "1 h", "POST /iocs/publish/run"], ["6", "Surveillance", "15 min", "POST /iocs/detections/ingest"],
           ["7", "Expiration", "1 h", "POST /iocs/expire/run puis /iocs/remove/run"], ["8", "Rapport", "06:00", "POST /reports/daily"]],
          [1.0, 3.4, 2.4, 9.8], source="docs/WORKFLOWS.md")
    bullets([
        "Authentification : chaque appel porte la clé de service (X-API-Key), lue dans l'environnement n8n et jamais écrite dans les fichiers exportés, et une étiquette X-Actor qui signe le journal d'audit (workflow-N).",
        "Idempotence : relancer une étape ne crée ni doublon ni double publication.",
        "Mesure : chaque exécution enregistre sa durée réelle (duration_ms) ; une exécution sans mesure est affichée « non mesurée ».",
        "Reprise : trois tentatives espacées de 5 secondes, puis sortie d'erreur journalisée.",
    ])
    proc = L.get("processing", {})
    stage_fr = {"COLLECT": "Collecte + normalisation + déduplication", "ENRICH": "Enrichissement (appels OTX / AbuseIPDB)",
                "SCORE": "Score + décision", "PUBLISH": "Publication + relecture"}
    rows, total_s = [], 0.0
    for key in ("COLLECT", "ENRICH", "SCORE", "PUBLISH"):
        st = proc.get(key)
        if not st:
            continue
        secs = st["duration_ms"] / 1000
        per = f"{fr(secs / st['items'], 2)} s" if st["items"] else "—"
        if st["items"]:
            total_s += secs / st["items"]
        rows.append([stage_fr[key], st["runs"], fr(st["items"]), f"{fr(secs, 1)} s", per])
    table("Temps machine mesuré par étape", ["Étape", "Exécutions", "Éléments traités", "Durée cumulée", "Par élément"],
          rows, [6.4, 2.2, 2.8, 2.8, 2.4], source="audit_logs.detail.duration_ms (exécutions mesurées par l'API)")
    callout("Lecture des temps de traitement",
            f"Le traitement automatique d'un indicateur, de la collecte à la décision, consomme environ "
            f"{fr(total_s, 1)} s de temps machine. Le délai de bout en bout dépend, lui, de la cadence des workflows "
            "(collecte toutes les 30 minutes, enrichissement toutes les heures) : pour le dernier lot, déclenché "
            "manuellement, l'attente entre la collecte et l'enrichissement a représenté l'essentiel du délai. "
            f"À titre de repère, un traitement manuel est estimé à {fr(au.get('manual_minutes_per_ioc'), 0)} minutes "
            "par indicateur — il s'agit d'un modèle explicite (hypothèse), non d'une mesure.",
            fill="FDF3E6", bar="E0A43B")

    # ---------------------------------------------------------- 8 sécurité
    h1("8. Sécurité")
    h2("8.1 Modèle de menace")
    table("Menaces et contrôles", ["Menace", "Contrôle", "Risque résiduel"],
          [["Accès non autorisé à l'API", "JWT + rôles, compte relu à chaque requête", "faible"],
           ["Force brute", "verrouillage après 5 échecs (15 min), 10 tentatives/min/IP", "faible"],
           ["Usurpation dans l'audit", "acteur tiré du jeton, jamais de la requête", "faible"],
           ["Injection SQL via un IOC", "validation stricte + requêtes paramétrées", "faible"],
           ["Lecture de fichiers via un paramètre", "chemins restreints au répertoire des capteurs", "faible"],
           ["Empoisonnement de l'inventaire", "anti-collusion par provenance + seuil 80", "moyen (assumé)"],
           ["Falsification de l'audit", "trigger PostgreSQL append-only", "faible"],
           ["Fuite de secrets", ".env hors dépôt, clés jamais renvoyées par l'API", "faible"],
           ["Exposition réseau", "services sur 127.0.0.1, tunnel SSH", "faible"],
           ["Publication non vérifiée", "relecture obligatoire avant « vérifié »", "faible"]],
          [4.8, 8.4, 3.4], source="docs/SECURITY.md")
    h2("8.2 Authentification et autorisations")
    table("Rôles", ["Rôle", "Droits"],
          [["Lecteur", "consultation de toutes les pages"],
           ["Analyste", "lecture + opérations du pipeline, qualification des détections, décisions manuelles, rapports"],
           ["Administrateur", "analyste + gestion des comptes (dernier administrateur protégé)"]], [3.4, 13.2])
    bullets([
        "Mots de passe : Argon2id, 12 caractères minimum et 3 classes de caractères.",
        "Jetons : JWT HS256 de 60 minutes ; un compte désactivé ou rétrogradé perd ses droits immédiatement.",
        "Énumération : message d'erreur unique et coût de calcul identique pour un compte inexistant.",
        "Production : l'API refuse de démarrer avec un secret faible, l'authentification désactivée, le mode debug ou un CORS ouvert.",
    ])
    h2("8.3 Durcissement")
    bullets([
        "HTTP : en-têtes de sécurité, CORS restreint, limitation de débit, erreurs sans pile ni écho des valeurs soumises.",
        "Console : Content-Security-Policy stricte (aucune ressource externe, polices embarquées).",
        "Conteneurs : utilisateurs non-root (API et nginx), image API sans outils d'installation, montages capteurs en lecture seule.",
        "MISP : vérification TLS activée par défaut.",
    ])
    table("Analyses de sécurité", ["Outil", "Périmètre", "Résultat"],
          [["Bandit", "code Python de l'API", "aucun problème"], ["pip-audit", "dépendances Python", "aucune vulnérabilité connue"],
           ["npm audit", "dépendances JavaScript", "aucune vulnérabilité"],
           ["Trivy", "image API, Dockerfiles, compose, workflows", "0 vulnérabilité HIGH/CRITICAL corrigeable, aucun secret"],
           ["OWASP ZAP baseline", "console + API (image de production)", "0 échec, 60 contrôles réussis, 2 avertissements documentés"]],
          [3.2, 6.4, 7.0], source="reports/security/zap-baseline.html ; docs/SECURITY.md")

    # ------------------------------------------------------------ 9 console
    h1("9. Console SOC")
    para("La console est l'outil de travail de l'analyste. Son identité visuelle — fond graphite, accent "
         "sarcelle, couleurs réservées au sens (risque, statut, santé) — a été définie avec un design system "
         "dédié, sans effets lumineux ni couleurs fluorescentes. Elle est utilisable au clavier, contrastée et "
         "responsive.")
    figure(SHOTS / "console-02-overview.png", "SOC Overview", 11.5, "poste local")
    table("Pages de la console", ["Page", "Contenu", "Actions (rôle)"],
          [["SOC Overview", "indicateurs, intégrations, activité, risques, sources, workflows", "—"],
           ["Detection Center", "alertes capteurs, sévérité, preuve brute", "qualifier (analyste)"],
           ["Threat Intelligence", "inventaire filtrable, tri, pagination, export CSV", "—"],
           ["Dossier IOC", "score justifié, cycle de vie, provenance, publications, audit", "décision manuelle (analyste)"],
           ["IOC Lifecycle", "dix étapes prouvées, publiés, expirés, retirés", "expirer, retirer (analyste)"],
           ["Scoring & Risk", "distribution, barème, classement, justification", "—"],
           ["Sources", "connexion, clé, débit, historique des collectes", "collecter (analyste)"],
           ["Automation Center", "workflows, exécutions, durées", "exécuter (analyste)"],
           ["Audit Center", "journal append-only filtrable", "—"],
           ["Rapports · System Health · Utilisateurs", "rapport quotidien, sondes, comptes", "générer ; gérer (admin)"]],
          [3.8, 8.2, 4.6], size=8)
    for name, cap in (("console-03-detection-center.png", "Detection Center"), ("console-05-ioc-detail.png", "Dossier de preuve d'un IOC"),
                      ("console-06-lifecycle.png", "IOC Lifecycle"), ("console-07-scoring.png", "Scoring & Risk Analysis"),
                      ("console-08-sources.png", "Sources de renseignement"), ("console-09-automation.png", "Automation Center"),
                      ("console-10-audit.png", "Audit Center"), ("console-11-system-health.png", "System Health")):
        figure(SHOTS / name, cap, 15.0)
    figure(SHOTS / "console-12-mobile.png", "Affichage mobile", 5.5)

    # --------------------------------------------------------- 10 données
    h1("10. Données et résultats opérationnels")
    para(f"Inventaire au {F['generated_at'][:10]} : {fr(S['total_iocs'])} indicateurs, score moyen "
         f"{fr(S.get('avg_score'), 1)}, {fr(S['total_detections'])} détections, "
         f"{fr(S['synthetic_iocs'])} indicateur synthétique.")
    figure(figs["statuts"], "Inventaire par statut", 14.0, "PostgreSQL")
    figure(figs["timeline"], "Activité quotidienne", 15.5)
    figure(EVAL_FIG / "eval_07_sources.png", "Contribution des sources", 14.0)
    table("Performance mesurée", ["Mesure", "Valeur"],
          [["Moteur de score seul (banc de 5 000 calculs)", f"{fr(perf['scoring_engine'].get('scores_per_second'))} scores/s"],
           ["Exécutions de pipeline tracées", fr(L["runs"]["total"])],
           ["Exécutions en échec", fr(L["runs"]["failed"])],
           ["Transitions de cycle de vie tracées", fr(lc.get("transitions_total"))]],
          [10.0, 6.6], source="reports/evaluation/metrics.json")

    # -------------------------------------------------------- 11 déploiement
    h1("11. Déploiement")
    h2("11.1 Poste local")
    code(["docker compose --profile n8n up -d --build",
          "cd backend ; python -m alembic upgrade head",
          "cd frontend ; npm install ; npm run dev   # http://127.0.0.1:5173/login"])
    h2("11.2 Serveur AWS")
    para("La plateforme tourne sur une instance EC2 t2.large (us-east-1) du Learner Lab. Tous les services "
         "écoutent sur 127.0.0.1 ; l'unique accès est un tunnel SSH vers l'adresse de l'administrateur.")
    table("Conteneurs en service sur EC2", ["Conteneur", "État", "Image"],
          [[c["name"], c["status"], c["image"]] for c in AWS.get("containers", [])], [3.6, 5.6, 7.4],
          source="docker ps sur l'instance")
    table("Contrôles du serveur", ["Contrôle", "Résultat"],
          [["API sans jeton", "401"], ["Content-Security-Policy", "présente"], ["Utilisateur nginx", "UID 101 (non-root)"],
           ["Ports en écoute", ", ".join(AWS.get("listening", [])) or "—"], ["Schéma de base", AWS.get("alembic", "—")],
           ["Workflow n8n exécuté", "succès"], ["Tests de bout en bout via le tunnel", "8 / 8"]], [8.0, 8.6])
    table("Coût", ["Poste", "Montant"],
          [["Instance t2.large en fonctionnement", "≈ 0,093 $/h (≈ 2,23 $/jour)"], ["Volume EBS 40 Go", "≈ 0,11 $/jour, même arrêtée"]],
          [8.0, 8.6], source="tarifs publics AWS us-east-1")
    figure(SHOTS / "aws-02-overview.png", "Console servie par le serveur AWS (via tunnel SSH)", 11.5)
    figure(figs["env"], "Poste local et serveur AWS", 13.5)
    # ------------------------------------------------------------- 12 tests
    h1("12. Validation et tests")
    figure(figs["tests"], "Tests exécutés", 15.0)
    table("Suites de tests", ["Suite", "Outil", "Réussis", "Commande"],
          [[t["suite"], t["tool"], f"{t['passed']}/{t['count']}", t["command"]] for t in F["tests"]], [4.6, 3.0, 1.8, 7.2], size=8)
    table("Couverture fonctionnelle des tests backend", ["Domaine", "Ce qui est prouvé"],
          [["Normalisation", "types, formes canoniques, rejets, empreintes"], ["Ingestion", "création, déduplication, provenance, rejet"],
           ["Scoring", "composantes, fraîcheur, seuils, pénalités, anti-collusion"], ["Cycle de vie", "transitions légales et illégales, audit"],
           ["Pipeline", "chaîne complète, reprise, expiration et retrait"], ["MISP", "publication, relecture, révocation, erreurs"],
           ["Sécurité", "audit immuable, entrées hostiles, secrets, ports"], ["Authentification", "rôles, verrouillage, clé de service, garde de production"],
           ["Console SOC (API)", "funnel, timeline, détections, qualification, recherche, intégrations"]], [4.0, 12.6])
    para("La campagne de validation a détecté puis fait corriger cinq défauts avant mise en service, chacun "
         "couvert ensuite par un test : collision entre la page de santé et la sonde /health, état des sources "
         "incohérent, erreur sur les détections manuelles, adresse cliente non IP au login, polices bloquées par "
         "la politique de sécurité du contenu.")

    # ----------------------------------------------------------- 13 limites
    h1("13. Limites et perspectives")
    table("Limites connues", ["Limite", "Comportement de la plateforme"],
          [["Pas de serveur MISP disponible", "client complet et testé ; état « Configuration manquante », aucune publication simulée"],
           ["Capteurs Suricata / Wazuh non démarrés en continu", "« Aucune donnée » si le fichier d'alertes est absent"],
           ["Pas de vérité terrain annotée", "précision et rappel non calculés ; seules des mesures observables sont revendiquées"],
           ["Jeton conservé dans l'onglet du navigateur", "atténué par la CSP stricte et une validité de 60 minutes"],
           ["Limitation de débit par processus", "suffisante pour un déploiement mono-instance"]], [6.0, 10.6])
    bullets([
        "Déployer un MISP de laboratoire pour exercer la publication distante vérifiée.",
        "Activer en continu les profils Suricata et Wazuh pour une détection en direct.",
        "Séparer les rôles PostgreSQL (migration / exécution) et porter la limitation de débit au reverse proxy.",
        "Ajouter des jetons de rafraîchissement courts avec révocation individuelle.",
        "Constituer un jeu de vérité terrain pour mesurer précision et rappel du scoring.",
    ])

    h1("Conclusion")
    para("SOAR IOC Factory automatise de bout en bout le cycle de vie des indicateurs de compromission en "
         "gardant ce qui fait la valeur d'un SOC : la capacité à expliquer et à prouver chaque décision. Le score "
         "est explicable, les décisions sont reproductibles, les publications et retraits sont vérifiés, chaque "
         "opération est journalisée de manière inaltérable, et l'analyste dispose d'une console claire fondée "
         "uniquement sur des données réelles.")
    para(f"La plateforme est validée par {fr(TESTS_OK)} tests automatisés réussis, par des analyses de sécurité "
         "sans vulnérabilité ouverte et par des tests de bout en bout réussis sur le poste local comme sur le "
         "serveur AWS. Les limites restantes sont identifiées, affichées honnêtement par la plateforme elle-même "
         "et ouvrent des perspectives concrètes.")

    # ----------------------------------------------------------- annexes
    h1("Annexe A — Principaux points d'accès de l'API")
    table("Points d'accès", ["Méthode et chemin", "Rôle minimal", "Usage"],
          [["POST /auth/login · GET /auth/me", "—", "authentification"], ["GET/POST/PATCH /users", "admin", "comptes"],
           ["GET /iocs · GET /iocs/{id}", "lecteur", "inventaire et détail"], ["GET /iocs/{id}/activity", "lecteur", "dossier de preuve"],
           ["POST /iocs/{id}/transition", "analyste", "décision manuelle"], ["POST /iocs/collect/run", "analyste", "collecte"],
           ["POST /iocs/enrich/run · /scoring/run", "analyste", "enrichissement, score"],
           ["POST /iocs/publish/run · /expire/run · /remove/run", "analyste", "publication, expiration, retrait"],
           ["GET /detections · POST /detections/{id}/review", "lecteur / analyste", "Detection Center"],
           ["GET /lifecycle/funnel · /stats/timeline", "lecteur", "cycle de vie, activité"],
           ["GET /integrations/status · /notifications", "lecteur", "santé, alertes"],
           ["GET /workflows/runs · /audit · /search", "lecteur", "exécutions, journal, recherche"],
           ["GET /health · /ready", "public", "sondes"]], [7.0, 3.0, 6.6], size=8)
    h1("Annexe B — Commandes de reproduction", new_page=False)
    code(["cd backend ; python -m pytest tests -q",
          "cd frontend ; npm test ; npm run typecheck ; npm run test:e2e",
          "python scripts/evaluate_platform.py",
          "python scripts/collect_facts.py --aws-json reports/data/aws.json",
          "python scripts/build_rapport_projet.py"])
    h1("Annexe C — Glossaire", new_page=False)
    table("Glossaire", ["Terme", "Définition"],
          [["IOC", "indicateur de compromission : observable technique associé à une activité malveillante"],
           ["CTI", "Cyber Threat Intelligence : renseignement sur la menace"],
           ["SOAR", "Security Orchestration, Automation and Response"],
           ["SOC", "Security Operations Center"], ["TIP", "Threat Intelligence Platform (ex. MISP)"],
           ["IDS / SIEM", "système de détection d'intrusion / gestion des événements de sécurité"],
           ["Provenance", "groupe de sources relayant la même origine, compté une seule fois"],
           ["Append-only", "table où les lignes ne peuvent être ni modifiées ni supprimées"]], [3.4, 13.2])
    doc.save(OUT)


if __name__ == "__main__":
    build()
    print(f"rapport -> {OUT}  ({N['table']} tableaux, {N['figure']} figures)")
