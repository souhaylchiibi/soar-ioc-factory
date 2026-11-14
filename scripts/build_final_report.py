"""Build the final Word report (jury deliverable) for the SOAR IOC Factory.

Design rules:
* every number comes from reports/evaluation/metrics.json, the live API or git;
* a missing artefact is reported, never replaced by an invented value;
* the document is self-contained: cover, TOC, headers/footers, 22 figures,
  ~30 numbered tables, 5 annexes.

Usage:  backend\\.venv\\Scripts\\python.exe scripts/build_final_report.py
Output: reports/RAPPORT_FINAL.docx
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any, Iterable, Optional

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

# ------------------------------------------------------------------ paths ---
ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "capture"
FIGURES = ROOT / "reports" / "figures"
EVAL_DIR = ROOT / "reports" / "evaluation"
OUT = ROOT / "reports" / "RAPPORT_FINAL.docx"

LOCAL_API = "http://127.0.0.1:8000/api/v1"
EC2_API = "http://127.0.0.1:8091/api/v1"      # via tunnel SSH
REPORT_DATE = "14 novembre 2026"

PRIMARY = RGBColor(0x0E, 0x5A, 0x8A)
SECONDARY = RGBColor(0x1F, 0x6F, 0xB2)
INK = RGBColor(0x33, 0x47, 0x5B)
GREY = RGBColor(0x5A, 0x6B, 0x7B)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

CONTENT_W = 16.6          # cm between margins
MARGIN_TOP = 2.2
MARGIN_BOTTOM = 2.0
MARGIN_LEFT = 2.3
MARGIN_RIGHT = 2.1

# ------------------------------------------------------------ live data ----
def api_get(base: str, path: str, timeout: float = 6.0) -> Optional[Any]:
    try:
        with urllib.request.urlopen(f"{base}{path}", timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def git(*args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                             text=True, timeout=20)
        return out.stdout.strip()
    except Exception:
        return ""


print("lecture des metriques ...")
metrics_path = EVAL_DIR / "metrics.json"
if not metrics_path.exists():
    sys.exit("reports/evaluation/metrics.json absent : lancer scripts/evaluate_platform.py")
metrics: dict[str, Any] = json.loads(metrics_path.read_text(encoding="utf-8"))

inv = metrics["inventory"]
ded = metrics["dedup"]
enr = metrics["enrichment"]
sco = metrics["scoring"]
pub = metrics["publication"]
det = metrics["detection"]
lif = metrics["lifecycle"]
perf = metrics["performance"]
aut = metrics["automation"]
aud = metrics["audit"]

local = api_get(LOCAL_API, "/iocs/stats/dashboard")
ec2 = api_get(EC2_API, "/iocs/stats/dashboard")
health = api_get(LOCAL_API, "/system/health")
COMMITS = git("rev-list", "--count", "HEAD") or "n/d"
TRACKED = len(git("ls-files").splitlines())

# --------------------------------------------------------- number format ---
def fr(value: Any, dec: int = 1) -> str:
    """French number: 51.9 -> 51,9 ; 2050.8 -> 2 050,8 ; None -> n/d."""
    if value is None:
        return "n/d"
    if isinstance(value, bool):
        return "oui" if value else "non"
    if isinstance(value, int):
        return f"{value:,}".replace(",", " ")
    if float(value).is_integer():
        return f"{int(value):,}".replace(",", " ")
    return f"{value:,.{dec}f}".replace(",", " ").replace(".", ",")


def kv(values: dict[str, Any]) -> str:
    if not values:
        return "aucun"
    return " · ".join(f"{k} {v}" for k, v in sorted(values.items(), key=lambda x: -x[1]))


def pct(value: Any, dec: int = 1) -> str:
    return f"{fr(value, dec)} %"


# ------------------------------------------------------------ docx utils ---
_TBLPR_ORDER = [
    "tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize",
    "tblStyleColBandSize", "tblW", "jc", "tblCellSpacing", "tblInd",
    "tblBorders", "shd", "tblLayout", "tblCellMar", "tblLook",
]
_TCPR_ORDER = [
    "cnfStyle", "tcW", "gridSpan", "hMerge", "vMerge", "tcBorders", "shd",
    "noWrap", "tcMar", "textDirection", "tcFitText", "vAlign", "hideMark",
]
_PPR_ORDER = [
    "pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr",
    "widowControl", "numPr", "suppressLineNumbers", "pBdr", "shd", "tabs",
    "suppressAutoHyphens", "kinsoku", "wordWrap", "overflowPunct",
    "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd",
    "snapToGrid", "spacing", "ind", "contextualSpacing", "mirrorIndents",
    "suppressOverlap", "jc", "textDirection", "textAlignment",
    "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr", "sectPr",
]


def _insert_ordered(parent, element, order: list[str]) -> None:
    tag = element.tag.split("}")[1]
    for existing in parent.findall(qn(f"w:{tag}")):
        parent.remove(existing)
    later = set(order[order.index(tag) + 1:])
    for child in list(parent):
        if child.tag.split("}")[1] in later:
            child.addprevious(element)
            return
    parent.append(element)


def _el(tag: str, **attrs: str):
    element = OxmlElement(f"w:{tag}")
    for key, value in attrs.items():
        element.set(qn(f"w:{key}"), str(value))
    return element


def shade_cell(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    _insert_ordered(tc_pr, _el("shd", val="clear", color="auto", fill=fill), _TCPR_ORDER)


def set_table_borders(table, color: str = "C9D6E2", size: int = 4) -> None:
    borders = _el("tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        borders.append(_el(edge, val="single", sz=size, space=0, color=color))
    _insert_ordered(table._tbl.tblPr, borders, _TBLPR_ORDER)


def set_table_layout(table, widths_cm: list[float]) -> None:
    table.autofit = False
    _insert_ordered(table._tbl.tblPr, _el("tblLayout", type="fixed"), _TBLPR_ORDER)
    for index, width in enumerate(widths_cm):
        table.columns[index].width = Cm(width)
        for row in table.rows:
            row.cells[index].width = Cm(width)


def set_cell_margins(table, top: int = 50, bottom: int = 50,
                     left: int = 90, right: int = 90) -> None:
    mar = _el("tblCellMar")
    for name, value in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        mar.append(_el(name, w=value, type="dxa"))
    _insert_ordered(table._tbl.tblPr, mar, _TBLPR_ORDER)


def repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tr_pr.append(_el("tblHeader", val="true"))


def cant_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tr_pr.append(_el("cantSplit", val="true"))


def add_field(paragraph, instruction: str, placeholder: str = "",
              size: Optional[float] = None, color: Optional[RGBColor] = None) -> None:
    run = paragraph.add_run()
    if size:
        run.font.size = Pt(size)
    if color is not None:
        run.font.color.rgb = color
    begin = _el("fldChar", fldCharType="begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    sep = _el("fldChar", fldCharType="separate")
    end = _el("fldChar", fldCharType="end")
    run._r.append(begin)
    run._r.append(instr)
    run._r.append(sep)
    if placeholder:
        text = OxmlElement("w:t")
        text.text = placeholder
        run._r.append(text)
    run._r.append(end)


def paragraph_border(paragraph, edge: str = "bottom", color: str = "0E5A8A",
                     size: int = 8, space: int = 4) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    borders = _el("pBdr")
    borders.append(_el(edge, val="single", sz=size, space=space, color=color))
    _insert_ordered(p_pr, borders, _PPR_ORDER)


# --------------------------------------------------------------- document ---
doc = Document()

section = doc.sections[0]
section.page_width = Cm(21)
section.page_height = Cm(29.7)
section.top_margin = Cm(MARGIN_TOP)
section.bottom_margin = Cm(MARGIN_BOTTOM)
section.left_margin = Cm(MARGIN_LEFT)
section.right_margin = Cm(MARGIN_RIGHT)
section.header_distance = Cm(1.0)
section.footer_distance = Cm(0.9)
section.different_first_page_header_footer = True

normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(10.5)
normal.font.color.rgb = RGBColor(0x1E, 0x1E, 0x1E)
normal.paragraph_format.space_after = Pt(6)
normal.paragraph_format.line_spacing = 1.12
normal.element.get_or_add_rPr().append(_el("lang", val="fr-FR"))

for name, size, color, before, after in (
    ("Heading 1", 17, PRIMARY, 0, 10),
    ("Heading 2", 12.5, SECONDARY, 12, 5),
):
    style = doc.styles[name]
    style.font.name = "Calibri"
    style.font.size = Pt(size)
    style.font.bold = True
    style.font.color.rgb = color
    style.paragraph_format.space_before = Pt(before)
    style.paragraph_format.space_after = Pt(after)
    style.paragraph_format.keep_with_next = True

# header / footer (not on the cover page) -----------------------------------
header = section.header
hp = header.paragraphs[0]
hp.paragraph_format.tab_stops.add_tab_stop(Cm(CONTENT_W), WD_TAB_ALIGNMENT.RIGHT)
hr = hp.add_run("SOAR IOC FACTORY · Rapport de projet")
hr.font.size = Pt(8)
hr.font.color.rgb = GREY
hr.font.name = "Calibri"
hp.add_run("\t")
hr2 = hp.add_run(REPORT_DATE)
hr2.font.size = Pt(8)
hr2.font.color.rgb = GREY
paragraph_border(hp, color="C9D6E2", size=4, space=2)

footer = section.footer
fp = footer.paragraphs[0]
fp.paragraph_format.tab_stops.add_tab_stop(Cm(CONTENT_W), WD_TAB_ALIGNMENT.RIGHT)
run = fp.add_run("Projet 3 — Usine à indicateurs de compromission")
run.font.size = Pt(8)
run.font.color.rgb = GREY
fp.add_run("\t")
run = fp.add_run("Page ")
run.font.size = Pt(8)
run.font.color.rgb = GREY
add_field(fp, " PAGE ", "1", size=8, color=GREY)
run = fp.add_run(" sur ")
run.font.size = Pt(8)
run.font.color.rgb = GREY
add_field(fp, " NUMPAGES ", "1", size=8, color=GREY)

# ask Word to refresh TOC and page fields when the file is opened
settings = doc.settings.element
settings.append(_el("updateFields", val="true"))

# ------------------------------------------------------------- primitives ---
def h1(text: str, new_page: bool = True) -> None:
    p = doc.add_heading(text, level=1)
    if new_page:
        p.paragraph_format.page_break_before = True
    p.paragraph_format.space_before = Pt(0)


def h2(text: str) -> None:
    doc.add_heading(text, level=2)


def para(text: str, size: float = 10.5, italic: bool = False, bold: bool = False,
         align: str = "justify", color: Optional[RGBColor] = None,
         space_after: float = 6, space_before: float = 0) -> None:
    p = doc.add_paragraph()
    p.alignment = {"justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
                   "center": WD_ALIGN_PARAGRAPH.CENTER,
                   "left": WD_ALIGN_PARAGRAPH.LEFT}[align]
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(space_before)
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.italic = italic
    run.bold = bold
    if color is not None:
        run.font.color.rgb = color


def bullets(items: Iterable[str], size: float = 10.5) -> None:
    for item in items:
        p = doc.add_paragraph(item, style="List Bullet")
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.08
        for run in p.runs:
            run.font.size = Pt(size)


def numbered(items: Iterable[str], size: float = 10.5) -> None:
    """Manual numbering: Word's "List Number" style would continue across sections."""
    for index, item in enumerate(items, start=1):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.75)
        p.paragraph_format.first_line_indent = Cm(-0.75)
        p.paragraph_format.space_after = Pt(2)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = p.add_run(f"{index}.  ")
        run.bold = True
        run.font.size = Pt(size)
        run.font.color.rgb = PRIMARY
        run = p.add_run(item)
        run.font.size = Pt(size)


TABLE_N = [0]


def table(caption: str, headers: list[str], rows: list[list[Any]],
          widths: Optional[list[float]] = None, source: Optional[str] = None,
          font_size: float = 8.5, align_first_left: bool = True) -> None:
    TABLE_N[0] += 1
    cap = doc.add_paragraph()
    cap.paragraph_format.space_before = Pt(8)
    cap.paragraph_format.space_after = Pt(4)
    cap.paragraph_format.keep_with_next = True
    run = cap.add_run(f"Tableau {TABLE_N[0]} — {caption}")
    run.bold = True
    run.font.size = Pt(9)
    run.font.color.rgb = PRIMARY

    table_obj = doc.add_table(rows=1, cols=len(headers))
    table_obj.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(table_obj)
    set_cell_margins(table_obj)

    header_cells = table_obj.rows[0].cells
    for index, label in enumerate(headers):
        cell = header_cells[index]
        shade_cell(cell, "0E5A8A")
        cell.paragraphs[0].paragraph_format.space_after = Pt(0)
        run = cell.paragraphs[0].add_run(label)
        run.bold = True
        run.font.size = Pt(font_size)
        run.font.color.rgb = WHITE
    repeat_header(table_obj.rows[0])
    cant_split(table_obj.rows[0])
    # keep OOXML order: cantSplit must precede tblHeader inside trPr
    tr_pr = table_obj.rows[0]._tr.get_or_add_trPr()
    header_el = tr_pr.find(qn("w:tblHeader"))
    split_el = tr_pr.find(qn("w:cantSplit"))
    if header_el is not None and split_el is not None:
        tr_pr.remove(header_el)
        split_el.addnext(header_el)

    for row_index, values in enumerate(rows):
        row = table_obj.add_row()
        cant_split(row)
        for index, value in enumerate(values):
            cell = row.cells[index]
            if row_index % 2 == 1:
                shade_cell(cell, "F2F7FB")
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            run = p.add_run(str(value))
            run.font.size = Pt(font_size)
            if index == 0 and align_first_left:
                run.bold = False

    if widths:
        set_table_layout(table_obj, widths)
    if source:
        note = doc.add_paragraph()
        note.paragraph_format.space_before = Pt(3)
        note.paragraph_format.space_after = Pt(10)
        run = note.add_run(f"Source : {source}")
        run.italic = True
        run.font.size = Pt(8)
        run.font.color.rgb = GREY
    else:
        doc.add_paragraph().paragraph_format.space_after = Pt(2)


def callout(title: str, body: str, fill: str = "EAF2F8") -> None:
    table_obj = doc.add_table(rows=1, cols=1)
    table_obj.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_obj.autofit = False
    set_table_layout(table_obj, [CONTENT_W])
    cell = table_obj.cell(0, 0)
    cell.width = Cm(CONTENT_W)
    shade_cell(cell, fill)
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = _el("tcBorders")
    borders.append(_el("left", val="single", sz=18, space=0, color="0E5A8A"))
    for edge in ("top", "bottom", "right"):
        borders.append(_el(edge, val="nil"))
    _insert_ordered(tc_pr, borders, _TCPR_ORDER)
    set_cell_margins(table_obj, top=110, bottom=110, left=170, right=150)

    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(title)
    run.bold = True
    run.font.size = Pt(9.5)
    run.font.color.rgb = PRIMARY

    p = cell.add_paragraph()
    p.paragraph_format.space_after = Pt(0)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    run = p.add_run(body)
    run.font.size = Pt(9.5)
    run.font.color.rgb = INK

    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(4)


def code(lines: list[str]) -> None:
    table_obj = doc.add_table(rows=1, cols=1)
    table_obj.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_obj.autofit = False
    set_table_layout(table_obj, [CONTENT_W])
    cell = table_obj.cell(0, 0)
    shade_cell(cell, "F4F6F8")
    set_table_borders(table_obj, color="DCE3EA", size=4)
    set_cell_margins(table_obj, top=90, bottom=90, left=130, right=130)
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.0
    for index, line in enumerate(lines):
        run = p.add_run(line)
        run.font.name = "Consolas"
        run.font.size = Pt(8)
        if index < len(lines) - 1:
            run.add_break()
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(4)


# -------------------------------------------------------------- figures ----
FIG_SPEC: list[tuple[str, Path, str, float]] = [
    ("ARCH", FIGURES / "architecture.png",
     "Architecture de la plateforme : quatre couches, une colonne de preuves PostgreSQL.", 15.5),
    ("F01", CAPTURES / "01-phase0-audit-environnement.jpg",
     "Audit de l'environnement de travail (Phase 0) : matériel, système, outils et accès aux sources.", 15.5),
    ("F02", CAPTURES / "02-phase2-swagger-socle.jpg",
     "Socle technique : documentation OpenAPI de l'API FastAPI et sondes de santé.", 15.5),
    ("F03", CAPTURES / "03-phase3-tests-104-verts.jpg",
     "Validation du moteur IOC par les tests automatisés (capture d'époque : 104 tests ; la suite en compte 177 à la livraison).", 15.5),
    ("F04", CAPTURES / "04-phase3-cycle-de-vie-demo.jpg",
     "Démonstration du cycle de vie sur un jeu synthétique de laboratoire (marqué is_synthetic), exécutée sur l'API réelle.", 15.5),
    ("F05", CAPTURES / "05-phase4-n8n-automatisation.jpg",
     "Les huit workflows n8n et leurs exécutions réelles, avec les effets observés en base.", 15.5),
    ("F06", CAPTURES / "06-phase5-integration-soc.jpg",
     "Intégration SOC : alertes Suricata et Wazuh produites sur les indicateurs publiés.", 15.5),
    ("F07", CAPTURES / "07-dashboard-general.jpg",
     "Dashboard général : indicateurs temps réel, lus sur l'API.", 15.5),
    ("F08", CAPTURES / "07b-dashboard-graphiques.jpg",
     "Dashboard : distribution des scores, répartition par type et évolution temporelle.", 15.5),
    ("F09", CAPTURES / "08-scoring-classement.jpg",
     "Page Scoring : classement des indicateurs par score décroissant.", 15.5),
    ("F10", CAPTURES / "08b-scoring-detail-explicatif.jpg",
     "Scoring explicable : détail des cinq composantes et des pénalités d'un score.", 15.5),
    ("F11", CAPTURES / "09-ioc-detail.jpg",
     "Fiche d'un indicateur : identité, score, sources et verdicts d'enrichissement.", 15.5),
    ("F12", CAPTURES / "09b-ioc-cycle-de-vie.jpg",
     "Fiche d'un indicateur : historique des transitions avec acteur et déclencheur.", 15.5),
    ("F13", CAPTURES / "10-system-health.jpg",
     "Page System Health : base de données, migrations, trigger d'audit et clés API.", 15.5),
    ("F14", FIGURES / "eval_01_cycle_de_vie.png",
     "Répartition des 174 indicateurs par étape du cycle de vie.", 14.6),
    ("F15", FIGURES / "eval_02_scores.png",
     "Distribution des scores et seuils de décision : rejet < 50, surveillance 50–79, publication ≥ 80.", 14.6),
    ("F16", FIGURES / "eval_03_entonnoir.png",
     "Entonnoir du cycle de vie : transitions réellement observées en base.", 14.6),
    ("F17", FIGURES / "eval_04_enrichissement.png",
     "Verdicts d'enrichissement par fournisseur (AlienVault OTX, AbuseIPDB).", 14.6),
    ("F18", FIGURES / "eval_05_collecte_dedup.png",
     "Volume collecté et qualité : créations, mises à jour, doublons écartés et rejets.", 14.6),
    ("F19", FIGURES / "eval_06_automatisation.png",
     "Temps par indicateur : modèle manuel (hypothèse explicite) contre plateforme (mesuré).", 14.6),
    ("F20", FIGURES / "eval_07_sources.png",
     "Contribution de chaque source de threat intelligence à l'inventaire.", 14.6),
    ("F21", CAPTURES / "11-aws-dashboard-ec2.jpg",
     "Le dashboard exécuté sur l'instance EC2, atteint par tunnel SSH (aucun port public).", 15.5),
]
FIG_INDEX = {key: pos for pos, (key, *_rest) in enumerate(FIG_SPEC)}
FIG_DONE: list[str] = []


def figure(key: str) -> None:
    spec = next(item for item in FIG_SPEC if item[0] == key)
    _key, path, caption, width = spec
    assert key not in FIG_DONE, f"figure {key} deja posee"
    FIG_DONE.append(key)
    if not path.exists():
        p = doc.add_paragraph(f"[figure absente : {path.name}]", style="Intense Quote")
        p.runs[0].italic = True
        return
    doc.add_picture(str(path), width=Cm(width))
    shape = doc.inline_shapes[-1]
    # tall "scrolling" captures must never exceed the printable height;
    # resizing must be done on both axes to preserve the aspect ratio.
    MAX_FIG_H = Cm(22.0)
    if shape.height > MAX_FIG_H:
        scale = MAX_FIG_H / shape.height
        shape.height = MAX_FIG_H
        shape.width = int(shape.width * scale)
    image_par = doc.paragraphs[-1]
    image_par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    image_par.paragraph_format.space_before = Pt(6)
    image_par.paragraph_format.space_after = Pt(4)
    image_par.paragraph_format.keep_with_next = True
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(12)
    run = cap.add_run(f"Figure {FIG_INDEX[key] + 1} — {caption}")
    run.italic = True
    run.font.size = Pt(8.5)
    run.font.color.rgb = GREY


# ================================================================== COVER ===
for _ in range(5):
    doc.add_paragraph()

kicker = doc.add_paragraph()
kicker.alignment = WD_ALIGN_PARAGRAPH.LEFT
run = kicker.add_run("PROJET 3  ·  USINE À INDICATEURS DE COMPROMISSION")
run.font.size = Pt(10)
run.font.bold = True
run.font.color.rgb = SECONDARY

title = doc.add_paragraph()
title.paragraph_format.space_before = Pt(10)
run = title.add_run("SOAR IOC\nFACTORY")
run.font.size = Pt(40)
run.font.bold = True
run.font.color.rgb = PRIMARY
run.font.name = "Calibri"

subtitle = doc.add_paragraph()
subtitle.paragraph_format.space_before = Pt(6)
run = subtitle.add_run("Automatiser le cycle de vie des indicateurs\nde compromission, sans jamais mentir sur leur état")
run.font.size = Pt(14)
run.font.color.rgb = INK

rule = doc.add_paragraph()
rule.paragraph_format.space_before = Pt(10)
rule.paragraph_format.space_after = Pt(18)
paragraph_border(rule, size=12, color="0E5A8A", space=1)

label = doc.add_paragraph()
run = label.add_run("RAPPORT DE PROJET")
run.font.size = Pt(11)
run.font.bold = True
run.font.color.rgb = GREY

meta = doc.add_table(rows=0, cols=2)
set_table_borders(meta, color="FFFFFF", size=2)
for key, value in (
    ("Candidat", "Souhayl Chouaibi"),
    ("Contexte", "Projet 3 — usine à indicateurs (cycle de vie des IOC)"),
    ("Environnement", "ThinkPad T480s · Windows · WSL2 · Docker · AWS Academy Learner Lab"),
    ("Date", REPORT_DATE),
    ("Version", f"Dépôt Git — {COMMITS} commits · {TRACKED} fichiers suivis"),
):
    cells = meta.add_row().cells
    cells[0].width = Cm(3.6)
    cells[1].width = Cm(12.0)
    run = cells[0].paragraphs[0].add_run(key.upper())
    run.font.size = Pt(8)
    run.font.bold = True
    run.font.color.rgb = GREY
    run = cells[1].paragraphs[0].add_run(value)
    run.font.size = Pt(10)
    run.font.color.rgb = INK
    for cell in cells:
        cell.paragraphs[0].paragraph_format.space_after = Pt(3)
set_table_layout(meta, [3.6, 12.4])

doc.add_paragraph()
doc.add_paragraph()

stats = doc.add_table(rows=2, cols=4)
stats.alignment = WD_TABLE_ALIGNMENT.CENTER
set_table_borders(stats, color="FFFFFF", size=2)
set_cell_margins(stats, top=120, bottom=120, left=60, right=60)
for index, (value, label_text) in enumerate((
    ("177", "tests automatisés"),
    ("174", "indicateurs évalués"),
    ("25", "routes API"),
    ("22", "figures"),
)):
    cell = stats.cell(0, index)
    shade_cell(cell, "F2F7FB")
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run(value)
    run.font.size = Pt(22)
    run.font.bold = True
    run.font.color.rgb = PRIMARY
    cell2 = stats.cell(1, index)
    shade_cell(cell2, "F2F7FB")
    p = cell2.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run(label_text)
    run.font.size = Pt(8)
    run.font.color.rgb = GREY
set_table_layout(stats, [4.0, 4.0, 4.0, 4.0])

note = doc.add_paragraph()
note.paragraph_format.space_before = Pt(14)
run = note.add_run(
    "Document généré automatiquement depuis le dépôt : chaque chiffre est lu dans "
    "reports/evaluation/metrics.json, dans l'API ou dans Git."
)
run.italic = True
run.font.size = Pt(8)
run.font.color.rgb = GREY

# ==================================================================== TOC ===
toc_title = doc.add_paragraph()
toc_title.paragraph_format.page_break_before = True
toc_title.paragraph_format.space_after = Pt(14)
run = toc_title.add_run("Sommaire")
run.font.size = Pt(20)
run.font.bold = True
run.font.color.rgb = PRIMARY

toc_par = doc.add_paragraph()
add_field(toc_par, ' TOC \\o "1-2" \\h \\z \\u ',
          "Le sommaire se génère à l'ouverture du document (F9 pour actualiser).",
          size=10, color=INK)

hint = doc.add_paragraph()
hint.paragraph_format.space_before = Pt(10)
run = hint.add_run(
    "Astuce : à l'ouverture, Word propose de mettre à jour les champs — accepter. "
    "Sinon, sélectionner ce sommaire et appuyer sur F9."
)
run.italic = True
run.font.size = Pt(8)
run.font.color.rgb = GREY

# --------------------------------------------------------- list of figures ---
fig_title = doc.add_paragraph()
fig_title.paragraph_format.page_break_before = True
fig_title.paragraph_format.space_after = Pt(12)
run = fig_title.add_run("Table des figures")
run.font.size = Pt(20)
run.font.bold = True
run.font.color.rgb = PRIMARY

para(
    "Les vingt-deux illustrations de ce rapport sont toutes des preuves : quatorze captures "
    "d'écran prises sur la plateforme réelle, sept graphiques générés depuis PostgreSQL par "
    "scripts/evaluate_platform.py et un schéma d'architecture construit depuis le code et les "
    "fichiers de déploiement.",
    size=9.5, color=GREY, space_after=10,
)
for pos, (key, path, caption, _width) in enumerate(FIG_SPEC, start=1):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.left_indent = Cm(0.2)
    run = p.add_run(f"Figure {pos}")
    run.bold = True
    run.font.size = Pt(9)
    run.font.color.rgb = PRIMARY
    run = p.add_run(f" — {caption}")
    run.font.size = Pt(9)
    run.font.color.rgb = INK
    run = p.add_run(f"  [{path.name}]")
    run.font.size = Pt(7.5)
    run.font.color.rgb = GREY

# ============================================================== 1. RESUME ===
h1("1. Résumé exécutif")

h2("1.1 Le problème")
para(
    "Un indicateur de compromission (IOC) n'a de valeur que s'il est encore vrai au moment "
    "où on l'utilise. Or les flux publics produisent des volumes importants d'adresses, de "
    "domaines, d'URL et d'empreintes dont une partie est dupliquée, périmée ou non corroborée. "
    "Traité manuellement, ce flux devient une file d'attente : l'analyste recopie des valeurs, "
    "cherche des doublons, ouvre trois interfaces, attribue un score « au feeling », publie dans "
    "une liste de blocage — et personne ne peut reconstituer, trois semaines plus tard, pourquoi "
    "telle adresse s'y trouvait encore."
)
para(
    "Le problème n'est donc pas seulement le volume. C'est la perte de traçabilité : sans "
    "journal, sans règle de notation explicite et sans vérification des actions, une usine à "
    "indicateurs devient une boîte noire qui propage des erreurs à la vitesse de l'automatisation."
)

h2("1.2 La réponse")
para(
    "SOAR IOC Factory automatise les dix étapes du cycle de vie — collecte, normalisation, "
    "déduplication, enrichissement, notation, décision, publication, surveillance, expiration, "
    "retrait vérifié — en conservant la preuve de chaque étape. La plateforme est construite "
    "autour d'une règle simple : une incertitude ne doit jamais être transformée en verdict. "
    "Un fournisseur muet n'est pas « bénin », une publication n'est « vérifiée » qu'après "
    "relecture, et un retrait n'est prononcé qu'une fois la révocation confirmée."
)
para(
    "Techniquement : API FastAPI (Python 3.11) et PostgreSQL 16, huit workflows n8n exportés "
    "en JSON, tableau de bord React/TypeScript de treize pages, intégrations Suricata et Wazuh "
    "en conditions réelles, client MISP complet mais serveur non déployé, déploiement Docker "
    "Compose sur une instance EC2 existante accessible uniquement par tunnel SSH."
)

h2("1.3 Chiffres clés")
table(
    "Indicateurs mesurés sur la plateforme (instantané du 14 novembre 2026).",
    ["Mesure", "Valeur", "Où la vérifier"],
    [
        ["Indicateurs en base", "174", "metrics.json · inventory"],
        ["Indicateurs notés et expliqués", "174 (100 %)", "score_breakdown persisté"],
        ["Score moyen / médian / p95", "51,9 / 52 / 64", "metrics.json · scoring"],
        ["Décisions : publier / surveiller / rejeter", "1 / 89 / 83", "metrics.json · decisions"],
        ["Taux de déduplication", "16,6 % (35 doublons / 211)", "metrics.json · dedup"],
        ["Couverture d'enrichissement", "79,9 % (139 / 174)", "metrics.json · enrichment"],
        ["Détections rapprochées / faux positifs", "16 sur 2 IOC / 0", "metrics.json · detection"],
        ["Latence à chaud (ingestion → score)", "43,8 s sur 65 IOC", "metrics.json · performance"],
        ["Tests automatisés", "177 au vert (~42 s)", "pytest · docs/TESTING.md"],
        ["Surface d'exposition publique", "aucun port applicatif", "security group + tests"],
    ],
    widths=[7.6, 4.6, 4.4],
    source="reports/evaluation/metrics.json, API /iocs/stats/dashboard et suite pytest.",
)

h2("1.4 Ce qui est démontré, ce qui ne l'est pas")
para("Sont démontrés, avec une preuve reproductible :", bold=True, space_after=2)
bullets([
    "le cycle complet exécuté sur des données réelles, jusqu'au retrait vérifié d'un indicateur (2 050,8 s, 7 transitions) ;",
    "une notation explicable : les 174 indicateurs portent le détail chiffré de leurs cinq composantes ;",
    "un journal d'audit append-only, protégé par un trigger PostgreSQL et par des tests qui tentent de le modifier ;",
    "huit workflows n8n réellement exécutés, avec contrôle d'idempotence et reprise après panne ;",
    "un déploiement EC2 sans aucun port applicatif exposé, l'accès passant par un tunnel SSH ;",
    "177 tests exécutés sur un vrai PostgreSQL, dont 27 tests de sécurité.",
])
para("Ne sont pas démontrés, et ne sont donc pas revendiqués :", bold=True,
     space_after=2, space_before=4)
bullets([
    "la précision et le rappel de la détection : ils exigeraient un jeu de vérité terrain annoté, absent ici ;",
    "l'intégration MISP de bout en bout : le client est testé contre un serveur simulé, le serveur n'est pas déployé ;",
    "les collecteurs abuse.ch (URLhaus, ThreatFox, MalwareBazaar) : la clé fournie a été refusée par le serveur ;",
    "les tests unitaires du frontend, les tests de charge et un test d'intrusion : non réalisés.",
])

callout(
    "Trois natures de chiffres, jamais mélangées",
    "Mesuré : lu dans PostgreSQL ou par l'API (inventaire, scores, latences, détections). "
    "Hypothèse : le modèle manuel de comparaison (17 min par IOC), posé explicitement dans "
    "scripts/evaluate_platform.py et modifiable — ce n'est pas un historique. Non mesurable : "
    "la précision et le rappel, faute de vérité terrain. Le rapport emploie ces trois "
    "catégories sans les confondre.",
)

# =========================================================== 2. CONTEXTE ===
h1("2. Contexte et problématique")

h2("2.1 L'indicateur de compromission")
para(
    "Un IOC est un artefact observable associé à une activité malveillante : adresse IP, nom de "
    "domaine, URL, empreinte de fichier (MD5, SHA-1, SHA-256). Sa valeur opérationnelle est "
    "double : il permet de détecter une compromission (recherche rétrospective, règles de "
    "détection) et d'anticiper (blocage, surveillance). Sa pertinence décroît avec le temps : "
    "une infrastructure malveillante change d'adresse en quelques jours, un domaine est abandonné, "
    "une empreinte reste stable plus longtemps."
)
para(
    "Les sources sont hétérogènes : flux communautaires (Feodo Tracker, blocklist.de), plateformes "
    "ouvertes (urlscan.io, AlienVault OTX), échanges sectoriels (MISP), fournisseurs commerciaux. "
    "Chacune a son format, sa fiabilité, sa latence et ses doublons. Le rôle d'une usine à "
    "indicateurs est de transformer cette matière première hétérogène en un inventaire unique, "
    "qualifié, daté et exploitable par les capteurs."
)

h2("2.2 Quatre défauts structurels")
table(
    "Les défauts que la plateforme doit corriger, et leur conséquence opérationnelle.",
    ["Défaut", "Manifestation", "Conséquence si non traité"],
    [
        ["Duplication et chambres d'écho",
         "Le même IOC arrive par trois flux, parfois revendiqué par des sources qui se recopient.",
         "Un score gonflé artificiellement et des listes de blocage redondantes."],
        ["Obsolescence",
         "Un domaine reste dans l'inventaire alors que son infrastructure a été démantelée.",
         "Des alertes qui consomment du temps d'analyste sans risque réel."],
        ["Opacité de la décision",
         "Un score est attribué sans que l'on sache quelle composante l'a produit.",
         "Impossible de contester, d'auditer ou d'améliorer la règle."],
        ["Actions non vérifiées",
         "Une publication est déclarée réussie sans relecture ; un retrait est supposé fait.",
         "La plateforme affirme un état faux — le pire défaut pour un outil de sécurité."],
    ],
    widths=[4.2, 6.6, 5.8],
    source="analyse de conception — docs/ARCHITECTURE.md.",
)

h2("2.3 Ce qu'une usine à indicateurs doit garantir")
bullets([
    "Une forme canonique par indicateur, pour que la déduplication soit déterministe.",
    "Une décision reproductible : mêmes entrées, mêmes règles, même résultat.",
    "Une explication persistée : le détail du score est stocké, pas recalculé à l'affichage.",
    "Une idempotence complète : rejouer un workflow ne crée ni doublon ni double publication.",
    "Une vérification des effets : publication relue, révocation confirmée, retrait conditionné.",
    "Un journal inaltérable de toutes les opérations, lisible par un tiers.",
])

h2("2.4 Périmètre et hors-périmètre")
para(
    "Le projet est un laboratoire mono-utilisateur exécuté sur un poste de travail et sur une "
    "instance EC2 d'un environnement d'apprentissage. Il ne bloque aucune infrastructure réelle : "
    "Suricata tourne en mode IDS (alerte), jamais en mode inline avec rejet de paquets. Les "
    "indicateurs synthétiques éventuels portent le drapeau is_synthetic en base ; l'inventaire "
    "livré n'en contient aucun."
)
para(
    "Sont hors périmètre : la production d'un flux commercial, l'intégration à un SOC réel, "
    "la haute disponibilité, l'authentification multi-utilisateur de l'API et le déploiement "
    "d'un serveur MISP. Ces points sont traités comme des limites assumées au chapitre 18."
)

# ========================================================== 3. EXIGENCES ===
h1("3. Exigences")

h2("3.1 Les dix étapes du cycle de vie")
table(
    "Chaque étape exigée, son implémentation et sa preuve.",
    ["#", "Étape", "Implémentation", "Preuve"],
    [
        ["1", "Collecte", "backend/app/collectors/ · POST /iocs/collect/run",
         "audit_logs COLLECT (8 exécutions)"],
        ["2", "Normalisation", "services/normalization.py · POST /iocs/normalize/run",
         "176 événements NORMALIZE"],
        ["3", "Déduplication", "empreinte SHA-256 « TYPE:value », contrainte unique",
         "35 événements DEDUP"],
        ["4", "Enrichissement", "enrichment/{otx,abuseipdb}.py · POST /iocs/enrich/run",
         "149 résultats, 12 erreurs isolées"],
        ["5", "Notation", "scoring/engine.py · POST /iocs/scoring/run",
         "174 scores expliqués, policy v1"],
        ["6", "Décision", "seuils 80 / 50 · lifecycle/machine.py",
         "1 publier · 89 surveiller · 83 rejeter"],
        ["7", "Publication", "POST /iocs/publish/run et /publish/misp/run",
         "2 publications, 1 vérifiée"],
        ["8", "Surveillance", "integrations/{suricata,wazuh}.py",
         "16 détections sur 2 IOC"],
        ["9", "Expiration", "champ expires_at · POST /iocs/expire/run",
         "1 transition EXPIRED"],
        ["10", "Retrait vérifié", "POST /iocs/remove/run",
         "1 transition REMOVED, révocation confirmée"],
    ],
    widths=[0.9, 3.0, 7.6, 5.1],
    source="code applicatif, routes OpenAPI et reports/evaluation/metrics.json.",
)

h2("3.2 Exigences de sécurité")
table(
    "Exigences de sécurité et contrôles associés.",
    ["Exigence", "Contrôle appliqué", "Preuve"],
    [
        ["Aucune exposition publique",
         "Publications Docker sur 127.0.0.1 uniquement ; security group sans règle 80/8000/5432/5678 ; accès par tunnel SSH.",
         "tests de ports, relecture du SG, test TCP depuis Internet"],
        ["Aucun blocage réel",
         "Suricata en mode IDS (alert) ; aucune règle DROP ; aucun appel à un équipement de filtrage.",
         "configuration Suricata, règles générées"],
        ["Aucun secret dans le dépôt",
         ".env et *.pem ignorés ; tests qui parcourent les fichiers suivis à la recherche de motifs de clés.",
         "test_security.py, git check-ignore"],
        ["Aucune action irréversible non vérifiée",
         "Publication relue depuis la cible ; REMOVED impossible sans révocation confirmée.",
         "services/misp_ops.py, tests dédiés"],
        ["Audit inaltérable",
         "Trigger PostgreSQL interdisant UPDATE et DELETE sur audit_logs.",
         "trg_audit_immutable, 3 tests"],
        ["Entrées hostiles",
         "Validation stricte, requêtes paramétrées, rejet plutôt que réparation.",
         "injection SQL et charges hostiles testées"],
    ],
    widths=[3.9, 8.0, 4.7],
    source="docs/SECURITY.md et backend/tests/test_security.py.",
)

h2("3.3 Exigences de traçabilité et d'automatisation")
bullets([
    "Chaque transition d'état enregistre l'acteur, le déclencheur, le score avant et après, et le motif.",
    "Chaque opération métier laisse une trace dans audit_logs, y compris les échecs.",
    "Chaque score est versionné : la politique v1 est identifiée dans score_history.",
    "Les workflows sont idempotents : un rejeu immédiat ne crée ni doublon ni double publication.",
    "La reprise après panne est naturelle : chaque étape filtre sur un statut, le tour suivant rattrape.",
    "L'ensemble est reproductible depuis le dépôt : migrations Alembic, compose, scripts, tests.",
])

h2("3.4 Critères d'acceptation")
numbered([
    "Un indicateur ne peut passer d'un état à un autre que si la transition est déclarée légale.",
    "Un score est toujours accompagné de ses cinq composantes et de ses pénalités.",
    "Une publication n'est marquée vérifiée qu'après relecture de la cible.",
    "Un retrait n'est prononcé que si la révocation est confirmée.",
    "Aucun port applicatif n'est joignable depuis Internet.",
    "La suite de tests passe intégralement sur un PostgreSQL réel, sans base de substitution.",
])

# ======================================================== 4. ARCHITECTURE ===
h1("4. Architecture")

h2("4.1 Vue d'ensemble")
para(
    "La plateforme est organisée en quatre couches : des collecteurs qui parlent aux sources, "
    "un noyau métier qui normalise, déduplique, enrichit, note et décide, des effecteurs qui "
    "publient et observent, et une couche de preuve (journal d'audit, historique de score, "
    "événements de cycle de vie). n8n déclenche les étapes ; il ne contient aucune règle métier."
)
para(
    "Le flux nominal s'écrit : sources → collecte → normalisation → déduplication → enrichissement "
    "→ notation → décision → publication → capteurs → détections → expiration → retrait vérifié. "
    "Chaque flèche correspond à une écriture en base et à une ligne d'audit."
)
figure("ARCH")
para(
    "La Figure 1 rend cette organisation lisible : les quatre couches s'enchaînent de haut en bas "
    "et chacune écrit ses preuves dans la colonne de droite. Les pointillés vers PostgreSQL ne "
    "sont pas décoratifs : ils matérialisent la règle de conception selon laquelle une étape sans "
    "trace en base n'est pas considérée comme exécutée."
)

h2("4.2 Composants")
table(
    "Composants de la plateforme.",
    ["Composant", "Rôle", "Technologie", "Emplacement"],
    [
        ["API", "Expose les opérations, porte les invariants (machine à états, notation, vérifications).",
         "FastAPI · SQLAlchemy 2 · Pydantic 2", "backend/app"],
        ["Base", "Inventaire, preuves, historique, audit.", "PostgreSQL 16", "13 tables"],
        ["Orchestrateur", "Planifie et rejoue les étapes, isole les erreurs.",
         "n8n · 8 workflows JSON", "workflows/n8n"],
        ["Tableau de bord", "Rend l'inventaire et les preuves lisibles.", "React 19 · TypeScript · Tailwind 4 · Recharts 3",
         "frontend/"],
        ["Capteurs", "Produisent les détections qui font foi.", "Suricata 8.0.8 (IDS) · Wazuh 4.12.0",
         "integrations/"],
        ["Client MISP", "Publie et révoque des attributs, avec relecture.", "REST maison, testé hors ligne",
         "integrations/misp.py"],
        ["Collecteurs", "Interrogent les sources et normalisent les erreurs.", "Python, HTTP",
         "collectors/"],
    ],
    widths=[3.0, 7.0, 4.3, 2.3],
    source="docs/ARCHITECTURE.md, arborescence du dépôt.",
)

h2("4.3 Flux d'une ingestion")
numbered([
    "Le collecteur interroge une source et transmet chaque élément brut à POST /iocs/ingest.",
    "La normalisation produit une forme canonique et une empreinte SHA-256 « TYPE:value ».",
    "Si l'empreinte existe déjà, l'élément met à jour la ligne existante et un événement DEDUP est journalisé ; sinon une ligne est créée au statut NEW.",
    "L'enrichissement interroge OTX et AbuseIPDB, avec un cache de 24 heures ; une erreur fournisseur est conservée, jamais traduite en verdict bénin.",
    "La notation calcule cinq composantes, applique les pénalités, persiste le détail et propose une décision.",
    "La décision fait passer l'indicateur à PUBLISHED, MONITORED ou REJECTED, avec un événement de cycle de vie.",
    "La publication écrit dans la liste de détection (et MISP si configuré), puis relit la cible pour vérifier.",
])

h2("4.4 Séparation orchestration / décision")
para(
    "n8n ne décide de rien. Il déclenche des routes, applique des retries et signale les échecs. "
    "Toutes les règles — transitions légales, seuils, vérification d'une publication — vivent "
    "derrière l'API, dans du code versionné et testé. Ce choix a une raison concrète : un workflow "
    "est modifiable par un utilisateur dans une interface graphique, sans revue de code. Si la "
    "règle « ne jamais retirer sans révocation confirmée » vivait dans un nœud n8n, elle pourrait "
    "disparaître en deux clics. Elle vit donc dans l'API, où un test la protège."
)

h2("4.5 Topologies de déploiement")
table(
    "Services et exposition réseau (compose local et instance EC2).",
    ["Service", "Port interne", "Publication", "Profil"],
    [
        ["API FastAPI", "8000", "127.0.0.1:8000", "socle"],
        ["PostgreSQL", "5432", "127.0.0.1:5432 (local) — non publié sur EC2", "socle"],
        ["Frontend nginx", "80", "127.0.0.1:80 (local et EC2)", "socle"],
        ["n8n", "5678", "127.0.0.1:5678", "n8n"],
        ["Suricata", "—", "aucun (job de rejeu PCAP)", "detection"],
        ["Wazuh manager", "1514/1515/55000", "aucun (réseau Docker)", "detection"],
    ],
    widths=[4.2, 3.4, 6.4, 2.6],
    source="docker-compose.yml, docker-compose.aws.yml et infrastructure/docker/.",
)
para(
    "En local, Docker Compose active les services par profils pour tenir dans la mémoire du poste "
    "(24 Go, dont environ 11 Go libres à l'audit) : le socle seul consomme moins de 1,5 Go, n8n "
    "ajoute 1 Go. Sur EC2, la même pile tourne derrière nginx ; aucun port n'est ouvert dans le "
    "security group, l'accès se fait par tunnel SSH."
)

# ============================================ 5. MODELE DE DONNEES ==========
h1("5. Modèle de données et cycle de vie")

h2("5.1 Les treize tables")
para(
    "Le schéma est volontairement explicite : chaque preuve a sa table, plutôt qu'un champ JSON "
    "fourre-tout. Les treize tables se répartissent en quatre familles."
)
bullets([
    "Référentiel : iocs (23 colonnes, dont score_breakdown et fingerprint), ioc_sources (provenance par source), intel_sources (fiabilité, groupe de provenance, quota), users.",
    "Preuves d'exécution : enrichments (verdict et charge brute), detections (capteur, règle, revue), publications (cible, statut, référence), score_history (score et politique).",
    "Cycle de vie : lifecycle_events (transition, acteur, déclencheur, score avant/après, vérification) et audit_logs (action, entité, détail, succès ou échec).",
    "Configuration et technique : scoring_policies (version active), reports (rapports quotidiens), alembic_version.",
])
para(
    "Le détail complet des colonnes figure en annexe B. La migration courante est dadb423768cb, "
    "appliquée en local comme sur EC2, et alembic check ne signale aucun écart entre les modèles "
    "et la base."
)

h2("5.2 Machine à états")
table(
    "Transitions autorisées par la machine à états (backend/app/lifecycle/machine.py).",
    ["État", "Peut aller vers", "Commentaire"],
    [
        ["NEW", "NORMALIZED · DUPLICATE · REJECTED", "entrée du pipeline"],
        ["NORMALIZED", "ENRICHED · REVIEW_REQUIRED · REJECTED", "forme canonique obtenue"],
        ["ENRICHED", "SCORED", "enrichissement terminé ou partiel"],
        ["SCORED", "PUBLISHED · MONITORED · REJECTED · REVIEW_REQUIRED · EXPIRED", "décision selon le score et la date"],
        ["PUBLISHED", "MONITORED · EXPIRED", "dépublication ou fin de vie"],
        ["MONITORED", "PUBLISHED · EXPIRED · REVIEW_REQUIRED", "réévaluation"],
        ["REVIEW_REQUIRED", "PUBLISHED · REJECTED · MONITORED", "arbitrage humain"],
        ["EXPIRED", "REMOVED", "retrait après vérification"],
        ["REMOVED", "—", "état terminal"],
        ["REJECTED", "—", "état terminal"],
        ["DUPLICATE", "—", "état terminal"],
    ],
    widths=[3.2, 8.6, 4.8],
    source="backend/app/lifecycle/machine.py (TRANSITIONS).",
)
para(
    "Toute transition non déclarée lève une erreur avant écriture. Les tests couvrent les cas "
    "légaux, les sauts illégaux (par exemple NORMALIZED → MONITORED) et les états terminaux. "
    "C'est cette machine qui rend la décision reproductible : elle ne dépend ni de l'ordre "
    "d'arrivée des workflows, ni d'un paramètre d'interface."
)

h2("5.3 Notation explicable")
para(
    "Le score est une somme pondérée de cinq composantes, diminuée de pénalités pour faux "
    "positifs connus. La somme des poids vaut 100 avant pénalités."
)
table(
    "Composantes du score et poids associés (politique v1).",
    ["Composante", "Poids", "Ce qu'elle mesure"],
    [
        ["Fiabilité de la source", "25", "réputation configurée de la source d'origine"],
        ["Fraîcheur", "20", "décroissance exponentielle, demi-vie propre à chaque type"],
        ["Sources indépendantes", "20", "nombre de groupes de provenance distincts, plafonné à 4"],
        ["Consensus d'enrichissement", "20", "convergence des verdicts OTX et AbuseIPDB"],
        ["Détections observées", "15", "alertes réellement produites par un capteur, saturant à 5"],
        ["Pénalité faux positif", "−20 par cas, plafond −40", "détection revue et confirmée comme bénigne"],
    ],
    widths=[4.6, 3.6, 8.4],
    source="backend/app/scoring/engine.py (DEFAULT_POLICY).",
)
para(
    "Deux choix méritent d'être soulignés. D'abord, les sources indépendantes sont comptées par "
    "groupe de provenance et non par flux : trois flux qui recopient OTX comptent pour une seule "
    "source. Ensuite, la fraîcheur décroît avec une demi-vie adaptée au type (3 jours pour une URL, "
    "7 pour une IP, 14 pour un domaine, 30 pour un MD5 ou un SHA-1, 60 pour un SHA-256)."
)
para(
    "Le détail est persisté dans score_breakdown, avec, pour chaque composante, les points obtenus, "
    "le maximum et une phrase d'explication. Le tableau de bord n'a donc rien à recalculer : il "
    "affiche la preuve."
)

h2("5.4 Seuils et conséquences")
table(
    "Seuils de décision et effet sur le cycle de vie.",
    ["Score", "Décision", "Statut", "Effet"],
    [
        ["≥ 80", "publier", "PUBLISHED", "écriture dans la liste de détection, puis relecture"],
        ["50 – 79", "surveiller", "MONITORED", "conservé pour observation, aucune publication"],
        ["< 50", "rejeter", "REJECTED", "conservé comme preuve, exclu de la publication"],
    ],
    widths=[2.2, 2.8, 2.8, 8.8],
    source="backend/app/core/config.py (score_threshold_publish / score_threshold_monitor).",
)
para(
    "Sur l'inventaire évalué, les quatre composantes hors détections totalisent en moyenne "
    "51,70 points, tandis que les détections n'apportent que 0,17 point. Autrement dit, le seuil "
    "de publication n'est atteint que par des indicateurs réellement observés par un capteur : "
    "empiler des sources ne suffit pas. C'est un comportement voulu, et c'est aussi la raison du "
    "faible taux de publication mesuré (1 indicateur sur 174)."
)
para(
    "La démonstration de la Figure 6 en donne l'illustration exacte : un indicateur plafonne à "
    "67/100 tant qu'aucune détection n'est constatée, puis atteint 82/100 lorsque les observations "
    "sont enregistrées — franchissant alors le seuil de publication."
)

# ========================================================== 6. PHASE 0 =====
h1("6. Phase 0 — Audit de l'environnement")
para(
    "L'audit a été conduit en lecture seule, avant toute installation. Il a servi à fixer les "
    "contraintes du projet, en particulier la mémoire disponible : Docker n'était pas installé, "
    "et la pile devait tenir sur un poste de 24 Go déjà chargé."
)
table(
    "Environnement relevé lors de l'audit initial.",
    ["Élément", "Valeur constatée", "Conséquence pour le projet"],
    [
        ["Processeur", "Intel Core i7-8550U, 4 cœurs / 8 threads", "pas de parallélisme lourd"],
        ["Mémoire", "24 Go, dont 11,4 Go libres", "profils Docker obligatoires"],
        ["Disque", "76,6 Go disponibles", "images Docker limitées au nécessaire"],
        ["Système", "Windows 10/11, WSL2 Ubuntu 24.04", "Docker Desktop avec backend WSL2"],
        ["Python", "3.11.9", "backend en python:3.11-slim"],
        ["Git", "2.51.0", "historique versionné dès la phase 0"],
        ["Node", "25.x", "frontend Vite"],
        ["Docker", "absent à l'audit", "installé ensuite (Docker Desktop)"],
        ["Accès sources", "Feodo 200 · OTX 200 · URLhaus 401 (clé désormais requise)", "collecteurs sans clé + OTX avec clé"],
    ],
    widths=[2.8, 7.4, 6.4],
    source="docs/PHASE0_AUDIT.md et capture de la Figure 2.",
)
figure("F01")
para(
    "Trois décisions découlent directement de cet audit : exclure OpenCTI (trop gourmand pour "
    "la mémoire disponible), faire tourner Suricata en rejeu de PCAP plutôt qu'en permanent, et "
    "n'activer n8n que par profil. Ces choix sont documentés et réversibles."
)

# ========================================================== 7. PHASE 1 =====
h1("7. Phase 1 — Conception")

h2("7.1 Décisions d'architecture")
table(
    "Décisions structurantes, alternatives écartées et raisons.",
    ["Décision", "Alternative écartée", "Raison"],
    [
        ["PostgreSQL 16", "SQLite", "contraintes, types énumérés, trigger d'audit, concurrence réelle"],
        ["Alembic", "création du schéma à la main", "schéma versionné, vérifiable (alembic check)"],
        ["FastAPI + Pydantic 2", "Flask", "contrat OpenAPI généré, validation stricte"],
        ["Machine à états dans le code", "règles dans n8n", "invariants testés, non modifiables par l'interface"],
        ["n8n comme orchestrateur", "planificateur maison", "visibilité des exécutions, reprise, export JSON"],
        ["MISP option B (client seul)", "serveur MISP complet", "MISP + OpenCTI dépassent la mémoire du poste"],
        ["Suricata en rejeu PCAP", "IDS permanent", "pas de capture temps réel fiable sous WSL2"],
        ["Profils Docker", "pile complète au démarrage", "tenir sous 11 Go de RAM disponibles"],
    ],
    widths=[4.6, 4.6, 7.4],
    source="docs/ARCHITECTURE.md.",
)

h2("7.2 Le modèle de données d'abord")
para(
    "Le schéma a été écrit avant le code métier : database/schema.sql puis les migrations Alembic. "
    "Cette antériorité a évité les colonnes ajoutées au fil de l'eau et a rendu possible une "
    "question simple dès le début : « où est la preuve de cette affirmation ? ». La réponse est "
    "toujours une table : lifecycle_events pour une transition, score_history pour un score, "
    "publications pour une publication, audit_logs pour une opération."
)

h2("7.3 Traçabilité par conception")
bullets([
    "lifecycle_events porte le score avant et après, l'acteur, le déclencheur et le détail de vérification.",
    "score_history conserve chaque calcul avec sa politique, ce qui permet de comparer deux versions.",
    "publications distingue verified, revoked et le détail de la relecture.",
    "audit_logs est append-only : un trigger refuse UPDATE et DELETE, y compris pour le propriétaire de la table.",
])

# ========================================================== 8. PHASE 2 =====
h1("8. Phase 2 — Socle technique")
para(
    "Le socle fournit l'API, la base, les migrations et les sondes de santé. Il est volontairement "
    "minimal : aucune fonctionnalité métier n'y figure, ce qui permet de le tester isolément."
)
bullets([
    "FastAPI avec logs JSON structurés, gestion centralisée des erreurs et contrat OpenAPI exposé sur /openapi.json.",
    "PostgreSQL 16 en conteneur, 13 tables, types énumérés pour les statuts et les niveaux de risque, index sur les colonnes de filtrage.",
    "Migrations Alembic versionnées ; alembic check ne détecte aucun écart entre modèles et base.",
    "Sondes /health (processus) et /ready (base) ; /api/v1/system/health agrège base, migrations, trigger d'audit, sources et clés.",
    "Docker Compose avec healthchecks et profils ; limites mémoire explicites par service.",
    "Les sondes renvoient HTTP 503 en cas de dégradation, ce qui rend une panne visible plutôt que silencieuse.",
])
figure("F02")

# ========================================================== 9. PHASE 3 =====
h1("9. Phase 3 — Moteur IOC")

h2("9.1 Normalisation")
para(
    "La normalisation produit une forme canonique par type, puis une empreinte SHA-256 de la chaîne "
    "« TYPE:value ». Cette empreinte est la clé de la déduplication : deux écritures différentes de "
    "la même adresse produisent la même empreinte."
)
bullets([
    "IP : parsing strict, rejet des adresses non routables (0.0.0.0, loopback, link-local, multicast). Les plages privées sont conservées volontairement — un IOC interne reste un IOC — et ce choix est documenté.",
    "Domaine : minuscules, suppression du point final, validation des labels ; une URL présentée dans un champ domaine est rejetée, jamais « réparée ».",
    "URL : schéma et hôte validés, normalisation limitée au strict nécessaire.",
    "Empreintes : MD5 (32), SHA-1 (40) et SHA-256 (64) reconnues par leur longueur, en hexadécimal minuscule.",
    "Toute valeur invalide est rejetée et journalisée : elle n'est jamais stockée telle quelle.",
])
para(
    "Cette sévérité a un coût assumé : quelques indicateurs valides sont perdus lorsque la source "
    "les déforme. Elle a un bénéfice mesurable : la déduplication est exacte et aucune valeur "
    "corrompue n'entre dans l'inventaire."
)

h2("9.2 Déduplication")
para(
    "La table iocs porte une contrainte d'unicité sur fingerprint. À l'ingestion, un élément dont "
    "l'empreinte existe déjà met à jour la ligne (dernière observation, sources) au lieu d'en créer "
    "une seconde ; un événement DEDUP est écrit dans audit_logs et duplicate_of peut référencer "
    "l'original. Sur 210 éléments bruts, 174 ont créé une ligne, 35 ont mis à jour une ligne "
    "existante et 1 a été rejeté, soit un taux de déduplication de 16,6 %."
)

h2("9.3 Enrichissement")
para(
    "Deux fournisseurs sont interrogés : AlienVault OTX (réputation, pulses) et AbuseIPDB "
    "(signalements d'adresses IP). Les réponses sont mises en cache 24 heures. Chaque appel est "
    "isolé : une erreur sur un fournisseur n'annule pas l'autre, elle est stockée comme erreur."
)
callout(
    "La règle qui protège le plus le projet",
    "Un fournisseur en panne n'est jamais interprété comme un verdict bénin. L'absence de réponse "
    "reste une absence : l'indicateur est enrichi partiellement, l'erreur est conservée, et le "
    "score ne reçoit aucun point de consensus indu. Sur l'inventaire, 12 appels ont échoué et sont "
    "visibles comme tels.",
)
para(
    "Résultat mesuré : 149 résultats stockés (140 OTX, 9 AbuseIPDB) pour 139 indicateurs enrichis, "
    "soit 79,9 % de couverture. Les verdicts OTX se répartissent en 99 « unknown », 27 « malicious » "
    "et 14 « suspicious » ; AbuseIPDB en 5 « unknown », 3 « suspicious » et 1 « benign »."
)

h2("9.4 Notation")
para(
    "Le moteur applique la politique v1 décrite au chapitre 5 : cinq composantes pondérées, "
    "pénalités de faux positifs, seuils de décision. Chaque composante renvoie ses points, son "
    "maximum et une explication en français. Le tout est persisté, ce qui rend le score contestable "
    "et comparable dans le temps."
)
para(
    "Le moteur est également mesuré à nu, sans base ni réseau : 5 000 itérations en 184,1 ms, soit "
    "27 159 scores par seconde (36,8 µs par score). Cette mesure isole le coût du calcul de celui "
    "des appels externes."
)

h2("9.5 Cycle de vie et vérification")
para(
    "La machine à états valide chaque transition. Deux invariants méritent d'être détaillés, car "
    "ils sont la différence entre une démonstration et un outil fiable."
)
bullets([
    "Publication vérifiée par relecture : après écriture dans la cible, la plateforme relit l'attribut ou la règle. Ce n'est qu'en cas de correspondance que publications.status passe à verified.",
    "Retrait conditionné : si la révocation n'est pas confirmée (l'attribut existe encore), le passage à REMOVED est refusé. L'indicateur reste EXPIRED, ce qui est exact.",
    "Client MISP absent : la route répond {\"status\": \"skipped\"} au lieu de simuler un succès.",
])
figure("F03")
figure("F04")

# ========================================================= 10. PHASE 4 =====
h1("10. Phase 4 — Automatisation n8n")

h2("10.1 Les huit workflows")
table(
    "Workflows exportés et planifiés (workflows/n8n/).",
    ["#", "Workflow", "Fichier", "Fréquence", "Route appelée"],
    [
        ["1", "IOC Collection", "01-ioc-collection.json", "30 min", "POST /iocs/collect/run?limit=50"],
        ["2", "IOC Normalization", "02-ioc-normalization.json", "30 min", "POST /iocs/normalize/run?limit=200"],
        ["3", "IOC Enrichment", "03-ioc-enrichment.json", "1 h", "POST /iocs/enrich/run?limit=50"],
        ["4", "IOC Scoring", "04-ioc-scoring.json", "30 min", "POST /iocs/scoring/run"],
        ["5", "IOC Publication", "05-ioc-publication.json", "1 h", "POST /iocs/publish/run?limit=100"],
        ["6", "IOC Monitoring", "06-ioc-monitoring.json", "15 min", "POST /iocs/detections/ingest + GET /detections/recent"],
        ["7", "IOC Expiration", "07-ioc-expiration.json", "1 h", "POST /iocs/expire/run puis /remove/run"],
        ["8", "IOC Reporting", "08-ioc-reporting.json", "quotidien 06:00", "POST /reports/daily"],
    ],
    widths=[0.9, 3.9, 4.4, 2.6, 4.8],
    source="docs/WORKFLOWS.md et workflows/n8n/*.json.",
)
para(
    "Les workflows sont générés par script et importables de façon idempotente : leurs "
    "identifiants sont stables, un réimport met à jour au lieu de dupliquer. Les huit exécutions "
    "de validation ont été réalisées en mode CLI et ont abouti au statut success, avec vérification "
    "des effets en base."
)

h2("10.2 Idempotence et reprise")
table(
    "Comportement en situation dégradée.",
    ["Situation", "Comportement observé"],
    [
        ["Workflow rejoué immédiatement", "aucun doublon : dédup par empreinte, publication existante détectée"],
        ["API momentanément indisponible", "le tour suivant rattrape ; chaque étape filtre sur un statut"],
        ["Source de collecte en panne", "les autres sources continuent ; l'échec est audité"],
        ["Enrichissement en erreur", "l'indicateur reste NORMALIZED et sera retenté"],
        ["Expiration sans publication", "REMOVED direct, après vérification qu'il n'y a rien à révoquer"],
        ["Révocation MISP non confirmée", "l'indicateur reste EXPIRED : jamais de REMOVED mensonger"],
    ],
    widths=[6.0, 10.6],
    source="docs/WORKFLOWS.md, section « reprise et idempotence ».",
)
para(
    "Point pratique : l'exécution en ligne de commande (n8n execute --id=…) exige que le workflow "
    "contienne un nœud Manual Trigger. C'est documenté pour éviter un faux diagnostic de panne "
    "lors d'un rejeu hors planification."
)
figure("F05")

# ========================================================= 11. PHASE 5 =====
h1("11. Phase 5 — Intégrations SOC")

h2("11.1 Suricata")
para(
    "Les règles de détection sont générées depuis les indicateurs au statut PUBLISHED, avec des "
    "identifiants propriétaires dans la plage 9xxxxx pour éviter toute collision avec un ruleset "
    "public. Suricata 8.0.8 est utilisé en mode IDS : il alerte, il ne bloque pas."
)
para(
    "La validation a été faite par rejeu d'un PCAP de laboratoire : règle chargée (1/1), alerte "
    "produite dans eve.json (signature 925288). Le rejeu est un job par lots dont le code de sortie "
    "est 0 par construction — un PCAP épuisé n'est pas une erreur — et ce comportement est "
    "documenté pour qu'il ne soit pas pris pour un échec silencieux."
)

h2("11.2 Wazuh")
para(
    "Seul le manager Wazuh 4.12.0 est déployé (logcollector, analysisd, remoted), l'indexer étant "
    "écarté pour économiser environ 2 Go de mémoire. Les alertes sont lues dans alerts.json, "
    "partagé en lecture seule avec l'API par un volume externe."
)
para(
    "Le manager a produit 204 alertes (dont le SCA natif) ; 4 ont été rattachées à l'indicateur "
    "suivi, et 2 indicateurs portent au total 16 correspondances. Les règles 5710 (utilisateur "
    "inexistant) et 5712 (force brute) ont été confirmées par wazuh-logtest avec l'adresse de "
    "l'IOC en source."
)

h2("11.3 MISP")
para(
    "Le client REST implémente le contrat officiel : /servers/getVersion, /events/add, "
    "/attributes/add, /attributes/view, /attributes/delete et /events/{id}/publish. La publication "
    "est vérifiée par relecture de l'attribut, et la révocation est confirmée avant tout retrait."
)
para(
    "Le serveur n'est pas déployé (option B) : sans MISP_URL et MISP_KEY, la route répond "
    "{\"status\": \"skipped\"} et aucun test ne touche le réseau. Dix-huit tests couvrent le client "
    "avec un transport simulé, y compris le cas où la révocation échoue."
)

h2("11.4 Synthèse")
table(
    "Intégrations : mode, preuve et limite.",
    ["Intégration", "Mode", "Preuve", "Limite assumée"],
    [
        ["Suricata 8.0.8", "IDS, rejeu PCAP", "1 règle chargée, 1 alerte (sid 925288), 2 détections rattachées",
         "pas de capture permanente"],
        ["Wazuh 4.12.0", "manager seul", "16 alertes réelles, règles 5710/5712 confirmées, 4 détections",
         "indexer non déployé"],
        ["MISP", "client REST", "18 tests simulés, relecture et refus de retrait non confirmé",
         "serveur non déployé"],
    ],
    widths=[3.2, 3.2, 6.8, 3.4],
    source="docs/SECURITY.md, docs/WORKFLOWS.md et backend/tests/test_misp.py.",
)
figure("F06")

# ========================================================= 12. PHASE 6 =====
h1("12. Phase 6 — Dashboard SOC")
para(
    "Le tableau de bord est une application React 19 en TypeScript strict, stylée avec Tailwind 4 "
    "et graphée avec Recharts 3. En production, nginx sert les fichiers statiques et relaie /api "
    "vers FastAPI. Toutes les valeurs affichées sont lues sur l'API : aucune statistique n'est "
    "calculée côté navigateur ni codée en dur."
)

h2("12.1 Treize routes")
table(
    "Pages du tableau de bord et objet de chacune.",
    ["Route", "Page", "Contenu"],
    [
        ["/", "Dashboard", "KPI temps réel, répartition, activité récente"],
        ["/inventory", "Inventory", "liste filtrable et paginée des indicateurs"],
        ["/sources", "Sources", "contribution et fiabilité des sources"],
        ["/scoring", "Scoring", "classement par score et détail explicatif"],
        ["/iocs/:id", "Fiche IOC", "identité, score, sources, détections, historique"],
        ["/lifecycle", "Lifecycle", "transitions et entonnoir du cycle de vie"],
        ["/published", "Published", "publications et état de vérification"],
        ["/monitoring", "Monitoring", "détections récentes par capteur"],
        ["/expired", "Expired", "indicateurs expirés en attente de retrait"],
        ["/workflows", "Workflows", "résumé des exécutions n8n"],
        ["/audit", "Audit", "journal d'audit filtrable"],
        ["/reports", "Reports", "rapports quotidiens générés"],
        ["/system-health", "System Health", "base, migrations, trigger, clés API"],
    ],
    widths=[3.4, 3.2, 10.0],
    source="frontend/src/App.tsx.",
)
para(
    "Le build TypeScript ne remonte aucune erreur et le build Vite aboutit. Les treize routes ont "
    "été parcourues manuellement, sans erreur dans la console du navigateur. Ce mode de validation "
    "est une limite : il n'existe pas de tests unitaires frontend (voir chapitre 18)."
)

h2("12.2 Captures")
figure("F07")
figure("F08")
figure("F09")
figure("F10")
figure("F11")
figure("F12")
figure("F13")

# ========================================================= 13. PHASE 7 =====
h1("13. Phase 7 — Évaluation")

h2("13.1 Méthode")
para(
    "L'évaluation n'est pas un discours sur la plateforme : c'est une lecture de PostgreSQL. Le "
    "script scripts/evaluate_platform.py exécute des requêtes d'agrégation, produit "
    "reports/evaluation/metrics.json, sept graphiques et un document de synthèse. Ce rapport "
    "consomme ce même fichier : les chiffres du texte et des tableaux sont donc ceux de la base, "
    "au moment de l'évaluation."
)
para(
    "Trois natures de valeurs coexistent et sont étiquetées comme telles : les mesures (lues en "
    "base), l'hypothèse de comparaison (le modèle manuel, explicite et modifiable) et ce qui n'est "
    "pas mesurable (précision, rappel, faute de vérité terrain)."
)

h2("13.2 Inventaire et qualité de la donnée")
table(
    "Inventaire, provenance et qualité (lecture directe de la base).",
    ["Mesure", "Valeur"],
    [
        ["Indicateurs en base", f"{inv['total_iocs']}"],
        ["Répartition par type", kv(inv["by_type"])],
        ["Niveaux de risque", kv(inv["by_risk"])],
        ["Statuts actuels", kv(inv["by_status"])],
        ["Indicateurs synthétiques (is_synthetic)", f"{inv['synthetic_iocs']}"],
        ["Éléments bruts collectés", f"{ded['raw_items_collected']}"],
        ["Créés / mis à jour / rejetés", f"{ded['created']} / {ded['updated']} / {ded['invalid_rejected']}"],
        ["Doublons écartés (événements DEDUP)", f"{ded['dedup_events']}"],
        ["Taux de déduplication", pct(ded["dedup_rate_pct"])],
        ["Contribution des sources", ", ".join(f"{s['name']} {s['ioc_count']}" for s in metrics["sources"])],
    ],
    widths=[7.4, 9.2],
    source="reports/evaluation/metrics.json (inventory, dedup, sources).",
)
para(
    "Deux enseignements. D'abord, la déduplication n'est pas un détail : un élément sur six reçu "
    "existait déjà, ce qui aurait produit autant de lignes redondantes et de scores artificiellement "
    "renforcés. Ensuite, l'inventaire est dominé par les domaines (93) et les adresses IP (56), "
    "ce qui correspond aux sources actives : urlscan produit surtout des domaines et des URL, "
    "blocklist.de et Feodo des adresses IP."
)

h2("13.3 Enrichissement et notation")
table(
    "Couverture d'enrichissement et résultats de notation.",
    ["Mesure", "Valeur"],
    [
        ["Indicateurs enrichis", f"{enr['iocs_enriched']} / {inv['total_iocs']} ({pct(enr['coverage_pct'])})"],
        ["Résultats stockés", f"{enr['results']} ({kv(enr['by_provider'])})"],
        ["Succès / erreurs fournisseurs", f"{pct(enr['provider_success_pct'])} / {enr['provider_errors']} erreurs"],
        ["Verdicts", kv(enr["by_verdict"])],
        ["Indicateurs notés", f"{sco['scored_iocs']} ({pct(sco['coverage_pct'], 0)})"],
        ["Score moyen / médian / p95", f"{fr(sco['avg'])} / {fr(sco['median'])} / {fr(sco['p95'])}"],
        ["Score minimum / maximum", f"{fr(sco['min'])} / {fr(sco['max'])}"],
        ["Scores expliqués", f"{sco['explainable_iocs']} ({pct(sco['explainability_pct'], 0)})"],
        ["Décisions", f"publier {sco['decisions']['publish']} · surveiller {sco['decisions']['monitor']} · rejeter {sco['decisions']['reject']}"],
        ["Politique de notation", f"{sco['policy']}"],
    ],
    widths=[7.4, 9.2],
    source="reports/evaluation/metrics.json (enrichment, scoring).",
)
para(
    "La distribution des scores est resserrée : 83 indicateurs sous 50, 87 entre 50 et 64, "
    "2 entre 65 et 79, 2 à 80 ou plus. La médiane (52) est proche de la moyenne (51,9), ce qui "
    "indique l'absence de valeurs aberrantes. Le score maximal, 82, correspond à un indicateur "
    "réellement observé par un capteur."
)

h2("13.4 Publication, détection et cycle de vie")
table(
    "Publications, détections et transitions.",
    ["Mesure", "Valeur"],
    [
        ["Publications enregistrées", f"{pub['total']}"],
        ["Vérifiées par relecture / révoquées", f"{pub['verified']} / {pub['revoked']}"],
        ["Publications actives", f"{pub['active']}"],
        ["Détections rapprochées", f"{det['total']} sur {det['iocs_with_detections']} indicateur(s)"],
        ["Détections par capteur", kv(det["by_sensor"])],
        ["Faux positifs observés", f"{det['false_positives']} ({pct(det['false_positive_rate_pct'])})"],
        ["Transitions journalisées", f"{lif['transitions_total']}"],
        ["Répartition des transitions", kv(lif["by_target_status"])],
        ["Cycle complet mesuré (NEW → REMOVED)",
         f"{fr(lif['full_cycles'][0]['seconds'])} s ({fr(lif['full_cycles'][0]['seconds'] / 60)} min), "
         f"{lif['full_cycles'][0]['transitions']} transitions" if lif["full_cycles"] else "aucun"],
    ],
    widths=[7.4, 9.2],
    source="reports/evaluation/metrics.json (publication, detection, lifecycle).",
)
para(
    "La couverture de détection est faible : 16 alertes sur 2 indicateurs, soit 1,1 % de "
    "l'inventaire. Ce n'est pas une anomalie de la plateforme, mais la conséquence de son principe : "
    "seuls les indicateurs publiés sont poussés vers les capteurs, et un seul l'a été. Le chiffre "
    "mesure donc la prudence du pipeline, pas sa performance de détection."
)
para(
    "Les 700 transitions journalisées incluent les 174 normalisations, 174 enrichissements et "
    "174 notations, plus 83 rejets, 91 passages en surveillance, 2 publications, 1 expiration et "
    "1 retrait. Le cycle complet observé (2 050,8 s, 7 transitions) correspond à un indicateur "
    "mené de sa création à son retrait vérifié."
)

h2("13.5 Performance")
table(
    "Latences et débit mesurés.",
    ["Mesure", "Valeur"],
    [
        ["Traitement à chaud (ingestion → score)",
         f"{fr(perf['hot_latency_avg_s'])} s en moyenne sur {perf['hot_latency_iocs']} indicateurs"],
        ["Débit du lot à chaud", f"{fr(perf['hot_batch_throughput_ioc_per_s'], 2)} indicateur/s"],
        ["Backlog repris après arrêt volontaire",
         f"{perf['backlog_iocs']} indicateurs, {fr(perf['backlog_latency_avg_h'])} h en moyenne"],
        ["Moteur de notation (CPU pur)",
         f"{fr(perf['scoring_engine']['scores_per_second'], 0)} scores/s "
         f"({fr(perf['scoring_engine']['us_per_score'])} µs/score)"],
    ],
    widths=[7.4, 9.2],
    source="reports/evaluation/metrics.json (performance).",
)
callout(
    "Ne pas confondre latence à chaud et backlog",
    "Le backlog (109 indicateurs, 163,6 h en moyenne) correspond à des indicateurs traités après "
    "un arrêt volontaire de la plateforme entre le 7 et le 14 novembre. Ce délai mesure une "
    "indisponibilité, pas une performance. Il est donc isolé et exclu de la latence à chaud, "
    "qui est de 43,8 s sur 65 indicateurs. Additionner les deux produirait un chiffre faux.",
)

h2("13.6 Automatisation : hypothèse et mesure")
table(
    "Modèle manuel de référence, décomposé (hypothèse explicite).",
    ["Tâche", "Temps par indicateur (min)"],
    [
        ["Collecte et vérification de la source", "1"],
        ["Normalisation et validation", "2"],
        ["Recherche de doublons", "2"],
        ["Enrichissement sur deux sources", "4"],
        ["Notation et décision", "3"],
        ["Publication et vérification", "4"],
        ["Journalisation et traçabilité", "1"],
        ["Total", "17"],
    ],
    widths=[11.0, 5.6],
    source="scripts/evaluate_platform.py (MANUAL_BASELINE).",
)
table(
    "Comparaison hypothèse / mesure.",
    ["Comparaison", "Valeur"],
    [
        ["Modèle manuel par indicateur (HYPOTHÈSE)", f"{fr(aut['manual_minutes_per_ioc'])} min"],
        ["Plateforme par indicateur (MESURÉ)", f"{fr(aut['automated_minutes_per_ioc'], 2)} min"],
        ["Facteur de réduction", f"×{fr(aut['time_reduction_factor'])}"],
        ["Charge manuelle pour cet inventaire (hypothèse)", f"{fr(aut['manual_hours_for_inventory'])} h"],
        ["Charge automatisée pour cet inventaire", f"{fr(aut['automated_hours_for_inventory'], 2)} h"],
        ["Temps économisé (hypothèse)", f"{fr(aut['hours_saved_for_inventory'])} h"],
    ],
    widths=[9.4, 7.2],
    source="reports/evaluation/metrics.json (automation).",
)
para(
    "Le facteur ×23,3 est le rapport entre un modèle posé et un temps mesuré. Le modèle (17 min) "
    "est une hypothèse de travail : il décrit ce qu'un analyste ferait sans automatisation, tâche "
    "par tâche, et il est modifiable dans le script. Les 0,73 min de la plateforme, elles, sont "
    "calculées à partir des horodatages en base. Présenter ce rapport comme un gain historique "
    "mesuré serait faux ; le présenter comme une projection argumentée est exact."
)

h2("13.7 Lecture des résultats")
bullets([
    "Le pipeline va au bout : 174 indicateurs normalisés, enrichis et notés, sans rupture de chaîne.",
    "La sélectivité est réelle : 47,7 % des indicateurs sont rejetés, faute de corroboration ou de fiabilité suffisante.",
    "La publication est rare (0,6 %) parce qu'elle exige des détections observées : c'est une décision de conception, pas un défaut.",
    "L'enrichissement couvre 79,9 % de l'inventaire ; les 20,1 % restants sont des types non couverts par les fournisseurs ou des appels en erreur, conservés comme tels.",
    "Aucun faux positif n'a été observé sur les 16 détections, mais seules les détections revues sont comptées : une détection non revue reste NULL.",
    "Le moteur de notation n'est pas le goulot d'étranglement (27 159 scores/s) : le temps est consommé par les appels réseau et la base.",
])

h2("13.8 Figures de l'évaluation")
figure("F14")
figure("F15")
figure("F16")
figure("F17")
figure("F18")
figure("F19")
figure("F20")

h2("13.9 Limites de l'évaluation")
bullets([
    "Précision et rappel ne sont pas calculables : aucun jeu de vérité terrain annoté n'est disponible. Seuls des proxys mesurables sont présentés.",
    "Les faux positifs ne sont comptés que pour les détections revues ; une détection non revue reste NULL et n'est jamais comptée comme bénigne.",
    "Le backlog est isolé au lieu d'être moyenné : il mesure une indisponibilité volontaire.",
    "Les collecteurs abuse.ch sont inactifs (clé refusée) : aucune donnée n'a été simulée pour compenser.",
    "L'évaluation porte sur un inventaire de 174 indicateurs : elle décrit ce laboratoire, pas un SOC à l'échelle.",
])

# ========================================================= 14. PHASE 8 =====
h1("14. Phase 8 — Déploiement AWS")
para(
    "Le déploiement réutilise une instance EC2 existante (t2.large, Ubuntu 24.04, us-east-1c) : "
    "aucune ressource n'a été créée pour le projet. L'accès à la démonstration passe par un tunnel "
    "SSH ; aucun port applicatif n'est ouvert dans le security group."
)
table(
    "Vérifications de déploiement et de non-exposition.",
    ["Vérification", "Résultat"],
    [
        ["Identité AWS", "compte [masqué : ID compte AWS], rôle voclabs (Learner Lab)"],
        ["Ressources créées", "0 — instance existante réutilisée"],
        ["Ports écoutés", "127.0.0.1:80 / :8000 / :5678 ; PostgreSQL non publié"],
        ["Règles security group (80/8000/5432/5678)", "aucune : exposition impossible"],
        ["SSH", "tcp/22 restreint à l'IP de l'administrateur (/32) ; 0.0.0.0/0 retirée le 14/11/2026"],
        ["Test depuis Internet", "TCP 80 → timeout"],
        ["Migrations", "head dadb423768cb appliquée"],
        ["Santé applicative", "system/health : healthy"],
        ["Données sur EC2", "94 IOC (73 actifs, 21 rejetés), score moyen 54,7"],
    ],
    widths=[6.6, 10.0],
    source="AWS CLI (describe-instances, describe-security-groups), tunnel SSH et API /system/health.",
)
para(
    "Le durcissement SSH a été appliqué dans le bon ordre : ajout de la règle /32, relecture du "
    "groupe confirmant la présence simultanée de l'ancienne et de la nouvelle règle, puis retrait "
    "de 0.0.0.0/0. Les identifiants des règles sont conservés dans docs/AWS_DEPLOYMENT.md, avec la "
    "procédure de retour arrière. L'IP de l'administrateur étant dynamique, la règle devra être "
    "mise à jour si elle change — c'est le comportement attendu d'un filtrage par IP."
)
para(
    "Coût : seule l'instance déjà lancée est facturée, environ 0,093 $/h, soit 2,23 $/jour quand "
    "elle tourne. Aucune autre ressource payante n'a été créée. Les identifiants de session du "
    "laboratoire expirent après quelques heures ; la procédure de redémarrage est documentée."
)
figure("F21")
callout(
    "Deux jeux de données distincts",
    "L'inventaire local (174 IOC) et l'inventaire EC2 (94 IOC) sont deux bases séparées, alimentées "
    "à des moments différents. Ils ne doivent être ni additionnés ni confondus : le rapport "
    "d'évaluation porte sur la base locale, la démonstration AWS sur l'instance.",
)

# ========================================================= 15. PHASE 9 =====
h1("15. Phase 9 — Documentation et exploitation")
para(
    "La documentation est traitée comme un livrable : elle est versionnée, et chaque guide répond "
    "à un besoin précis plutôt que de répéter le README."
)
table(
    "Documents livrés et public visé.",
    ["Document", "Contenu", "Public"],
    [
        ["README.md", "présentation, chiffres clés, démarrage rapide, structure", "jury, relecteur"],
        ["docs/INSTALLATION.md", "prérequis, variables, migrations, profils, dépannage", "exploitant"],
        ["docs/WORKFLOWS.md", "8 workflows, fréquences, routes, ID, reprise", "orchestrateur"],
        ["docs/SECURITY.md", "modèle de menace, contrôles, preuves, risques résiduels", "jury, RSSI"],
        ["docs/TESTING.md", "177 tests, répartition, zones non couvertes", "développeur"],
        ["docs/USER_GUIDE.md", "dashboard et API côté utilisateur", "analyste"],
        ["docs/ARCHITECTURE.md", "conception, modèle, choix techniques", "développeur"],
        ["docs/AWS_DEPLOYMENT.md", "déploiement, coûts, tunnel, durcissement, procédures", "exploitant"],
    ],
    widths=[4.6, 8.4, 3.6],
    source="arborescence docs/ et README.md.",
)
para(
    "La reproductibilité repose sur trois éléments : les migrations Alembic décrivent le schéma, "
    "les workflows sont exportés en JSON et réimportables, et les scripts d'évaluation et de "
    "génération de rapport sont dans le dépôt. Un relecteur peut donc reconstruire la plateforme "
    "et vérifier les chiffres."
)
para("Séquence de reprise, en quatre commandes :", bold=True, space_after=2)
code([
    "docker compose up -d --build",
    "docker compose exec api alembic upgrade head",
    "docker compose --profile n8n up -d",
    "backend\\.venv\\Scripts\\python.exe scripts\\evaluate_platform.py",
])
para(
    "Un relecteur pressé peut, en dix minutes : lire le README, ouvrir le dashboard, consulter la "
    "fiche d'un IOC et son détail de score, vérifier le journal d'audit, puis lancer pytest pour "
    "constater les 177 tests au vert."
)

# ========================================================== 16. SECURITE ===
h1("16. Sécurité")

h2("16.1 Modèle de menace")
table(
    "Menaces identifiées et contrôles correspondants.",
    ["Menace", "Contrôle", "Preuve"],
    [
        ["Exposition d'un service sur Internet",
         "publications Docker sur loopback ; aucune règle SG pour 80/8000/5432/5678 ; tunnel SSH",
         "test TCP externe, relecture du SG, test automatisé des ports"],
        ["Fuite de secret par le dépôt",
         ".env et *.pem ignorés ; motifs de clés recherchés dans les fichiers suivis",
         "test_security.py, git check-ignore"],
        ["Altération ou effacement de l'audit",
         "trigger PostgreSQL refusant UPDATE et DELETE sur audit_logs",
         "trg_audit_immutable, 3 tests dédiés"],
        ["Injection SQL via un IOC hostile",
         "validation stricte, requêtes paramétrées, rejet avant stockage",
         "charge « '; DROP TABLE iocs; -- » rejetée, table intacte"],
        ["Gonflement artificiel du score",
         "comptage par groupe de provenance, plafond de sources indépendantes",
         "test anti-collusion, colonne provenance_group"],
        ["Action irréversible non vérifiée",
         "publication relue, retrait conditionné à la révocation confirmée",
         "tests MISP, statut EXPIRED conservé si échec"],
        ["Saut d'état illégal",
         "machine à états explicite, erreur avant écriture",
         "23 tests de cycle de vie"],
    ],
    widths=[4.2, 7.6, 4.8],
    source="docs/SECURITY.md, backend/tests/test_security.py.",
)

h2("16.2 Contrôles et preuves")
bullets([
    "Aucun port applicatif exposé : les publications Docker sont liées à 127.0.0.1, et le security group de l'instance ne contient qu'une règle SSH vers une adresse /32.",
    "Aucun blocage réel : Suricata alerte, les règles générées ne contiennent pas d'action DROP, et aucun équipement de filtrage n'est appelé.",
    "Aucun secret versionné : les fichiers sensibles sont ignorés et un test parcourt les fichiers suivis à la recherche de motifs de clés.",
    "Audit append-only : le trigger refuse toute modification, y compris depuis le compte propriétaire ; les tests tentent l'UPDATE et le DELETE.",
    "Entrées hostiles : le pipeline rejette les valeurs invalides et les charges d'injection, sans jamais « réparer » une donnée douteuse.",
    "Moindre privilège : un rôle applicatif dédié, pas de superutilisateur pour l'API.",
])

h2("16.3 Risques résiduels")
table(
    "Risques résiduels, gravité et réponse.",
    ["Risque", "Gravité", "Réponse"],
    [
        ["API sans authentification", "moyenne en labo, élevée ailleurs",
         "assumé en mono-utilisateur sur loopback ; à corriger avant tout usage partagé"],
        ["IP administrateur dynamique", "faible",
         "SSH refusé si l'IP change ; procédure de mise à jour documentée, console EC2 en secours"],
        ["Pas de fail2ban ni de MFA", "faible",
         "surface réduite à une IP et à une clé ; recommandations listées"],
        ["Pas de test d'intrusion", "moyenne",
         "contrôles testés unitairement, mais aucune évaluation adversariale complète"],
        ["Mono-nœud, pas de sauvegarde testée", "moyenne",
         "volume PostgreSQL nommé ; restauration non exercée"],
    ],
    widths=[5.2, 4.4, 7.0],
    source="docs/SECURITY.md, section « risques résiduels ».",
)
para(
    "Aucun test d'intrusion n'a été conduit. Les contrôles sont vérifiés par des tests automatisés "
    "et par des relevés (security group, ports, trigger), ce qui ne remplace pas une évaluation "
    "adversariale."
)

# ============================================================= 17. TESTS ===
h1("17. Tests")
para(
    "La suite compte 177 tests, exécutés sur un PostgreSQL réel (base soar_ioc_test migrée par "
    "Alembic), et non sur SQLite. Ce choix a un coût — les tests sont plus lents — et un bénéfice : "
    "les contraintes, les types énumérés et le trigger d'audit sont réellement éprouvés."
)

h2("17.1 Répartition")
table(
    "Les 177 tests par module.",
    ["Module", "Tests", "Ce qu'il couvre"],
    [
        ["test_normalization.py", "35", "formes canoniques, rejets, empreintes"],
        ["test_security.py", "27", "audit immuable, entrées hostiles, sauts d'état, anti-collusion, secrets, ports"],
        ["test_lifecycle.py", "23", "transitions légales et illégales, états terminaux"],
        ["test_ingest.py", "21", "pipeline réel : dédup, rejets, audit, provenance"],
        ["test_scoring.py", "19", "explicabilité, décroissance, anti-collusion, décisions"],
        ["test_misp.py", "18", "client simulé, relecture, refus de retrait non confirmé"],
        ["test_providers.py", "16", "OTX et AbuseIPDB hors ligne, cas non applicables"],
        ["test_pipeline.py", "11", "chemin complet, expiration, résilience"],
        ["test_health.py", "7", "sondes, configuration, logs JSON"],
        ["Total", "177", "177 passed, 0 échec (~42 s)"],
    ],
    widths=[4.8, 1.8, 10.0],
    source="pytest --collect-only et docs/TESTING.md.",
)

h2("17.2 Ce que les tests ont réellement attrapé")
bullets([
    "une composante de score dépassant son poids maximal (score de 100 au lieu de 90) ;",
    "une URL présentée dans un champ domaine « réparée » silencieusement au lieu d'être rejetée ;",
    "une violation d'unicité sur ioc_sources : le lien n'était pas visible avant le flush (autoflush désactivé) ;",
    "un test d'immuabilité de l'audit qui abortait la transaction : rollback nécessaire entre l'UPDATE et le DELETE ;",
    "des colonnes detail et success sans valeur par défaut côté base ;",
    "un trigger d'audit append-only absent de la migration alors qu'il existait dans schema.sql.",
])
para(
    "Ces six défauts sont documentés dans la Figure 4, qui montre le rapport de tests d'époque avec "
    "leur symptôme et leur correction. Chacun produisait un résultat faux ou une preuve manquante, "
    "sans provoquer d'erreur visible."
)

h2("17.3 Ce qui n'est pas couvert")
table(
    "Zones non couvertes et raison.",
    ["Zone", "Raison", "Conséquence"],
    [
        ["Interface React", "pas de tests unitaires frontend", "validation par build et parcours manuel"],
        ["Charge et montée en charge", "laboratoire mono-poste", "débit mesuré sur 65 IOC seulement"],
        ["MISP réel", "serveur non déployé", "client testé contre un transport simulé"],
        ["abuse.ch", "clé refusée par le serveur", "collecteurs présents mais inactifs"],
        ["Test d'intrusion", "hors périmètre du laboratoire", "contrôles vérifiés, pas éprouvés adversarialement"],
        ["CI", "contrainte du laboratoire", "exécution locale documentée"],
    ],
    widths=[4.4, 5.6, 6.6],
    source="docs/TESTING.md.",
)
para("Commande d'exécution, avec le mot de passe lu dans .env sans l'afficher :", bold=True,
     space_after=2)
code([
    "cd backend",
    "$env:PYTHONPATH=\"$PWD\"; $env:POSTGRES_HOST=\"127.0.0.1\"; $env:POSTGRES_USER=\"soar\"",
    "$env:POSTGRES_PASSWORD=(Select-String -Path ..\\.env -Pattern '^POSTGRES_PASSWORD=(.+)$').Matches[0].Groups[1].Value",
    ".\\.venv\\Scripts\\python.exe -m pytest tests -q",
])

# ========================================================== 18. LIMITES ====
h1("18. Limites et perspectives")

h2("18.1 Limites assumées")
table(
    "Limites du projet, effet et réponse apportée.",
    ["Limite", "Effet", "Réponse"],
    [
        ["Pas de vérité terrain annotée", "précision et rappel non calculables", "proxys mesurés explicitement nommés"],
        ["Clé abuse.ch refusée", "URLhaus, ThreatFox et MalwareBazaar inactifs", "aucune donnée simulée en compensation"],
        ["MISP non déployé", "pas de publication externe réelle", "client complet, 18 tests, réponse skipped"],
        ["API sans authentification", "inutilisable en multi-utilisateur", "loopback uniquement, limite documentée"],
        ["Pas de tests frontend", "régressions visuelles possibles", "build strict et parcours manuel des 13 routes"],
        ["Pas de CI", "exécution manuelle des tests", "procédure documentée et reproductible"],
        ["Backlog de 109 IOC", "latence globale faussée", "isolé et exclu de la latence à chaud"],
        ["IP administrateur dynamique", "SSH refusé si l'IP change", "procédure de mise à jour, console en secours"],
        ["Deux inventaires séparés", "risque de confusion 174 / 94", "distinction explicite dans le rapport"],
        ["Mono-nœud", "pas de haute disponibilité", "assumé pour un laboratoire"],
    ],
    widths=[5.0, 5.6, 6.0],
    source="docs/SECURITY.md, docs/TESTING.md et évaluation.",
)

h2("18.2 Perspectives")
bullets([
    "Régénérer une clé abuse.ch pour activer trois collecteurs déjà codés.",
    "Déployer un serveur MISP et dérouler le cycle publication / révocation de bout en bout.",
    "Ajouter une authentification (jeton ou OIDC) avant tout usage partagé.",
    "Constituer un jeu de vérité terrain annoté pour mesurer précision et rappel.",
    "Ajouter une CI (pytest + build frontend) et des tests de composants React.",
    "Passer à trois nœuds (API, base répliquée, orchestration) pour la disponibilité.",
])

# =========================================================== 19. BILAN ====
h1("19. Bilan")
para(
    "Le projet livre une usine à indicateurs complète, exécutable et vérifiable. Les dix étapes du "
    "cycle de vie sont implémentées, automatisées par huit workflows, exposées par 25 routes et "
    "rendues lisibles par un tableau de bord de treize pages. Les 177 tests s'exécutent sur un "
    "PostgreSQL réel, et l'évaluation est une lecture de la base, non un commentaire."
)
para("Ce qui distingue le projet, en trois points :", bold=True, space_after=2)
numbered([
    "La plateforme refuse de mentir : une publication n'est vérifiée qu'après relecture, un retrait n'est prononcé qu'après confirmation de la révocation, un fournisseur muet n'est jamais un verdict bénin.",
    "Chaque décision est explicable : le détail du score est persisté, versionné et affiché, ce qui rend la règle contestable et améliorable.",
    "Chaque opération est traçable : le journal d'audit est append-only, protégé par un trigger et par des tests qui tentent de le corrompre.",
])
para(
    "Les limites sont réelles et énoncées : pas de précision ni de rappel sans vérité terrain, pas "
    "de serveur MISP, pas de collecteurs abuse.ch actifs, pas de tests frontend ni de CI. Elles "
    "dessinent les prochains travaux, sans invalider ce qui est démontré."
)
para(
    "En une phrase : la plateforme transforme un flux d'indicateurs bruyant en un inventaire daté, "
    "noté, expliqué et vérifié — et elle est capable de prouver, pièce par pièce, pourquoi chaque "
    "indicateur s'y trouve et pourquoi il en est sorti.",
)

# ============================================================ ANNEXE A =====
h1("Annexe A — Routes de l'API")
para(
    "Vingt-cinq chemins et vingt-sept opérations, tels qu'exposés par /openapi.json. Les routes "
    "d'administration sont volontairement accessibles sans authentification dans ce laboratoire "
    "mono-utilisateur (voir chapitre 18)."
)
ROUTES = [
    ("GET", "/health", "vivacité du processus"),
    ("GET", "/ready", "disponibilité (base de données)"),
    ("GET", "/api/v1/system/health", "santé agrégée : base, migrations, trigger, sources, clés"),
    ("GET", "/api/v1/iocs", "liste filtrée et paginée des indicateurs"),
    ("GET", "/api/v1/iocs/{ioc_id}", "fiche détaillée d'un indicateur"),
    ("PATCH", "/api/v1/iocs/{ioc_id}", "mise à jour contrôlée (revue, expiration, tags)"),
    ("POST", "/api/v1/iocs/{ioc_id}/transition", "transition explicite avec motif"),
    ("POST", "/api/v1/iocs/{ioc_id}/detections", "déclaration manuelle d'une détection"),
    ("GET", "/api/v1/iocs/detections/recent", "détections récentes"),
    ("POST", "/api/v1/iocs/detections/ingest", "ingestion des alertes capteurs"),
    ("GET", "/api/v1/iocs/lifecycle/events", "journal des transitions"),
    ("GET", "/api/v1/iocs/stats/dashboard", "KPI du tableau de bord"),
    ("GET", "/api/v1/iocs/stats/sources", "contribution des sources"),
    ("POST", "/api/v1/iocs/ingest", "ingestion unitaire d'un indicateur"),
    ("POST", "/api/v1/iocs/collect/run", "exécution de la collecte"),
    ("POST", "/api/v1/iocs/normalize/run", "exécution de la normalisation"),
    ("POST", "/api/v1/iocs/enrich/run", "exécution de l'enrichissement"),
    ("POST", "/api/v1/iocs/scoring/run", "exécution de la notation"),
    ("POST", "/api/v1/iocs/publish/run", "publication vers la liste de détection"),
    ("POST", "/api/v1/iocs/publish/misp/run", "publication vers MISP (ou skipped)"),
    ("POST", "/api/v1/iocs/expire/run", "expiration des indicateurs échus"),
    ("POST", "/api/v1/iocs/remove/run", "retrait vérifié"),
    ("GET", "/api/v1/audit", "journal d'audit filtrable"),
    ("GET", "/api/v1/audit/actions", "actions d'audit disponibles"),
    ("GET", "/api/v1/workflows/summary", "résumé des workflows et de leurs effets"),
    ("GET", "/api/v1/reports/daily", "consultation du rapport quotidien"),
    ("POST", "/api/v1/reports/daily", "génération du rapport quotidien"),
]
table(
    "Routes exposées par l'API.",
    ["Méthode", "Chemin", "Usage"],
    [[m, p, u] for m, p, u in ROUTES],
    widths=[2.0, 7.6, 7.0],
    font_size=8,
    source="GET /openapi.json (25 chemins, 27 opérations).",
)

# ============================================================ ANNEXE B =====
h1("Annexe B — Schéma des tables")
table(
    "Les treize tables de la base et leur rôle.",
    ["Table", "Rôle", "Colonnes clés"],
    [
        ["iocs", "inventaire des indicateurs", "type, value, status, score, fingerprint, score_breakdown, is_synthetic"],
        ["ioc_sources", "provenance de chaque indicateur", "ioc_id, source_id, first_seen_at, external_id"],
        ["intel_sources", "sources configurées", "name, kind, provenance_group, reliability, enabled"],
        ["users", "acteurs et rôles", "id, name, role"],
        ["enrichments", "résultats d'enrichissement", "ioc_id, provider, verdict, payload, fetched_at"],
        ["detections", "alertes rapprochées", "ioc_id, sensor, rule_id, matched_at, is_false_positive"],
        ["publications", "publications et révocations", "ioc_id, target, status, published_at, revoked_at"],
        ["score_history", "historique des scores", "ioc_id, score, breakdown, policy, computed_at"],
        ["scoring_policies", "versions de politique", "version, active, params"],
        ["lifecycle_events", "transitions d'état", "from_status, to_status, actor, triggered_by, verified"],
        ["audit_logs", "journal append-only", "action, entity_type, detail, success, occurred_at"],
        ["reports", "rapports quotidiens", "report_date, kind, payload, file_path"],
        ["alembic_version", "version du schéma", "version_num (dadb423768cb)"],
    ],
    widths=[3.6, 4.4, 8.6],
    source="information_schema.columns et database/migrations/.",
)

# ============================================================ ANNEXE C =====
h1("Annexe C — Commandes utiles")
para("Démarrage local de la pile :", bold=True, space_after=2)
code([
    "docker compose up -d --build",
    "docker compose exec api alembic upgrade head",
    "docker compose --profile n8n up -d          # orchestration",
    "docker compose --profile detection up -d    # Suricata / Wazuh",
])
para("Vérification de l'état :", bold=True, space_after=2)
code([
    "curl http://127.0.0.1:8000/api/v1/system/health",
    "curl http://127.0.0.1:8000/api/v1/iocs/stats/dashboard",
])
para("Évaluation et rapport :", bold=True, space_after=2)
code([
    "backend\\.venv\\Scripts\\python.exe scripts\\evaluate_platform.py",
    "backend\\.venv\\Scripts\\python.exe scripts\\build_final_report.py",
])
para("Tests :", bold=True, space_after=2)
code([
    "cd backend",
    "$env:PYTHONPATH=\"$PWD\"; $env:POSTGRES_HOST=\"127.0.0.1\"; $env:POSTGRES_USER=\"soar\"",
    "$env:POSTGRES_PASSWORD=(Select-String -Path ..\\.env -Pattern '^POSTGRES_PASSWORD=(.+)$').Matches[0].Groups[1].Value",
    ".\\.venv\\Scripts\\python.exe -m pytest tests -q",
])
para("Accès à la démonstration EC2 (tunnel uniquement) :", bold=True, space_after=2)
code([
    "ssh -i \"soar-ioc-key.pem\" -N -L 8091:127.0.0.1:80 ubuntu@<ip-publique>",
    "# puis http://127.0.0.1:8091/",
])

# ============================================================ ANNEXE D =====
h1("Annexe D — Inventaire des illustrations")
table(
    "Fichiers sources des vingt-deux figures.",
    ["N°", "Fichier", "Dossier", "Poids"],
    [[str(pos), path.name, path.parent.name + "/", f"{max(1, round(path.stat().st_size / 1024))} Ko"]
     for pos, (_key, path, _caption, _width) in enumerate(FIG_SPEC, start=1)],
    widths=[1.4, 8.6, 4.0, 2.6],
    font_size=8,
    source="capture/ et reports/figures/.",
)

# ============================================================ ANNEXE E =====
h1("Annexe E — Glossaire")
table(
    "Termes employés dans le rapport.",
    ["Terme", "Définition"],
    [
        ["IOC", "indicateur de compromission : IP, domaine, URL ou empreinte de fichier."],
        ["Usine à indicateurs", "chaîne qui collecte, qualifie et publie des IOC de façon automatisée."],
        ["Empreinte (fingerprint)", "SHA-256 de « TYPE:value », clé de déduplication."],
        ["Enrichissement", "ajout de contexte par des sources tierces (OTX, AbuseIPDB)."],
        ["Score explicable", "score dont chaque composante est persistée avec son explication."],
        ["Groupe de provenance", "origine réelle d'une source ; deux flux d'un même groupe comptent pour une source."],
        ["NEW / NORMALIZED / ENRICHED / SCORED", "états du pipeline avant décision."],
        ["PUBLISHED", "indicateur poussé vers une cible de détection, après vérification."],
        ["MONITORED", "indicateur conservé et observé, sans publication."],
        ["REJECTED", "indicateur écarté, conservé comme preuve."],
        ["EXPIRED", "indicateur échu, en attente de retrait."],
        ["REMOVED", "indicateur retiré, révocation confirmée."],
        ["REVIEW_REQUIRED", "cas ambigu nécessitant un arbitrage humain."],
        ["Audit append-only", "journal en ajout seul, protégé par un trigger."],
        ["IDS", "système de détection d'intrusion : alerte sans blocage."],
        ["Tunnel SSH", "redirection de port locale vers un service distant non exposé."],
    ],
    widths=[6.0, 10.6],
    source="docs/ARCHITECTURE.md, docs/WORKFLOWS.md et docs/USER_GUIDE.md.",
)

# ============================================================== FINAL ======
footer_end = doc.add_paragraph()
footer_end.alignment = WD_ALIGN_PARAGRAPH.CENTER
footer_end.paragraph_format.space_before = Pt(24)
run = footer_end.add_run("— Fin du rapport —")
run.font.size = Pt(9)
run.font.color.rgb = GREY

OUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(OUT)

# ------------------------------------------------------------ validation ---
assert len(FIG_DONE) == len(FIG_SPEC), f"figures posees: {len(FIG_DONE)}/{len(FIG_SPEC)}"
assert FIG_DONE == [spec[0] for spec in FIG_SPEC], "ordre des figures incoherent"

from docx import Document as _Document

check = _Document(OUT)
headings = [p.text for p in check.paragraphs if p.style.name == "Heading 1"]
text_all = "\n".join(
    [p.text for p in check.paragraphs]
    + [c.text for t in check.tables for r in t.rows for c in r.cells]
)
problems = [token for token in ("None", "TODO", "[figure absente", "lorem", "n/d")
            if token in text_all]

print(f"Rapport genere : {OUT}")
print(f"  sections H1   : {len(headings)}")
print(f"  tableaux      : {TABLE_N[0]} numerotes ({len(check.tables)} objets table)")
print(f"  figures       : {len(FIG_DONE)} (images: {len(check.inline_shapes)})")
print(f"  paragraphes   : {len(check.paragraphs)}")
print(f"  taille        : {OUT.stat().st_size / 1024:.0f} Ko")
print(f"  commits       : {COMMITS} | fichiers suivis : {TRACKED}")
print(f"  jetons suspects: {problems if problems else 'aucun'}")
if problems:
    sys.exit(1)
