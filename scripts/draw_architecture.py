"""Draw the architecture diagram used in the final report (Figure 1).

The picture is a faithful summary of the running stack: no invented component.
Sources: docker-compose.yml, backend/app (packages), workflows/n8n (8 JSON),
frontend/src/App.tsx (13 routes), database/migrations (13 tables).

Usage:  backend\\.venv\\Scripts\\python.exe scripts\\draw_architecture.py
Output: reports/figures/architecture.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "figures" / "architecture.png"

PRIMARY = "#0E5A8A"
SECONDARY = "#1F6FB2"
INK = "#33475B"
GREY = "#5A6B7B"
LIGHT = "#EAF2F8"
LIGHTER = "#F2F7FB"
WHITE = "#FFFFFF"
AMBER = "#B7791F"

plt.rcParams["font.family"] = "DejaVu Sans"

fig, ax = plt.subplots(figsize=(8.6, 5.6), dpi=220)
ax.set_xlim(0, 101)
ax.set_ylim(0, 66)
ax.axis("off")

FLOW_W = 67.5          # right edge of the flow column
EVIDENCE_X = 70.6      # left edge of the evidence column


def box(x, y, w, h, title, body="", fc=WHITE, ec=SECONDARY, lw=1.1,
        dashed=False, title_size=9, body_size=6.8, title_color=None,
        body_y=0.30):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0,rounding_size=1.1",
        linewidth=lw, edgecolor=ec, facecolor=fc,
        linestyle=(0, (3.2, 2.2)) if dashed else "solid",
        zorder=2,
    ))
    cx = x + w / 2
    if body:
        ax.text(cx, y + h * 0.68, title, ha="center", va="center",
                fontsize=title_size, fontweight="bold",
                color=title_color or PRIMARY, zorder=3)
        ax.text(cx, y + h * body_y, body, ha="center", va="center",
                fontsize=body_size, color=INK, linespacing=1.3, zorder=3)
    else:
        ax.text(cx, y + h / 2, title, ha="center", va="center",
                fontsize=title_size, fontweight="bold",
                color=title_color or PRIMARY, zorder=3)


def layer_label(y, text):
    ax.text(0.8, y, text.upper(), ha="left", va="bottom", fontsize=7.4,
            fontweight="bold", color=GREY, zorder=3)


def arrow(x1, y1, x2, y2, dashed=False, color=SECONDARY, lw=1.1):
    ax.add_patch(FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle="-|>", mutation_scale=9,
        linewidth=lw, color=color, zorder=1,
        linestyle=(0, (2.6, 2.0)) if dashed else "solid",
        shrinkA=0, shrinkB=0,
    ))


# ---------------------------------------------------------- 1. sources -----
layer_label(59.8, "1 · sources")
SOURCES = [
    ("Feodo Tracker", "flux public"),
    ("blocklist.de", "flux public"),
    ("urlscan.io", "recherche"),
    ("AlienVault OTX", "API + clé"),
    ("abuse.ch", "clé refusée — inactif"),
]
width = 12.7
gap = 0.9
for index, (name, note) in enumerate(SOURCES):
    x = 0.6 + index * (width + gap)
    inactive = name == "abuse.ch"
    box(x, 53.4, width, 5.8, name, note,
        fc="#F4F4F4" if inactive else LIGHT,
        ec=GREY if inactive else "#7FA8C9",
        dashed=inactive, title_size=8.1, body_size=6.3,
        title_color=GREY if inactive else PRIMARY)

# ------------------------------------------------- 2. collecte et n8n ------
layer_label(48.4, "2 · collecte et orchestration")
box(0.6, 41.4, FLOW_W, 6.4,
    "Collecteurs Python  ·  n8n",
    "4 sources actives  ·  8 workflows planifiés (JSON versionnés)  ·  reprise après panne",
    fc=WHITE, ec=SECONDARY, title_size=9, body_size=6.8)

# ------------------------------------------------------- 3. noyau métier ---
layer_label(35.2, "3 · noyau métier — API")
STAGES = [
    ("Normaliser", "forme canonique\nempreinte SHA-256"),
    ("Dédupliquer", "empreinte unique\nfusion, pas doublon"),
    ("Enrichir", "OTX · AbuseIPDB\ncache 24 h"),
    ("Noter", "5 composantes\npénalités explicites"),
    ("Décider", "seuils 80 / 50\nmachine à états"),
]
stage_w = (FLOW_W - 4 * 0.8) / 5
for index, (name, note) in enumerate(STAGES):
    x = 0.6 + index * (stage_w + 0.8)
    box(x, 25.4, stage_w, 9.2, name, note,
        fc=LIGHTER, ec=PRIMARY, title_size=8.4, body_size=6.3, body_y=0.29)

# ----------------------------------------------------- 4. effets ----------
layer_label(19.9, "4 · effets, capteurs et consommateurs")
EFFECTS = [
    ("Publier", "liste de détection\nrelecture = preuve"),
    ("Surveiller", "Suricata IDS · Wazuh\n16 détections"),
    ("Expirer / retirer", "révocation\nconfirmée"),
    ("Exposer", "dashboard React\n13 pages · API"),
]
effect_w = (FLOW_W - 3 * 0.8) / 4
for index, (name, note) in enumerate(EFFECTS):
    x = 0.6 + index * (effect_w + 0.8)
    box(x, 11.6, effect_w, 8.0, name, note,
        fc=WHITE, ec=SECONDARY, title_size=8.3, body_size=6.4, body_y=0.29)

# ----------------------------------------------------- 5. accès ------------
box(0.6, 1.6, FLOW_W, 6.6,
    "Accès unique : tunnel SSH",
    "Aucun port applicatif ouvert sur Internet\n"
    "Docker publié sur 127.0.0.1  ·  security group limité au SSH /32",
    fc="#FBF6EC", ec=AMBER, title_size=8.2, body_size=6.3,
    title_color="#8A5A12", body_y=0.30)

# --------------------------------------------------- 6. preuves -----------
box(EVIDENCE_X, 11.6, 29.0, 47.6, "", fc="#FBFDFE", ec=PRIMARY, lw=1.2, dashed=True)
ax.text(EVIDENCE_X + 14.5, 56.6, "PREUVES", ha="center", va="center", fontsize=8.6,
        fontweight="bold", color=PRIMARY, zorder=3)
ax.text(EVIDENCE_X + 14.5, 54.2, "PostgreSQL 16 · 13 tables", ha="center",
        va="center", fontsize=6.5, color=GREY, zorder=3)

EVIDENCE = [
    ("iocs", "23 colonnes · score_breakdown"),
    ("ioc_sources", "provenance par source"),
    ("enrichments", "verdict + charge brute"),
    ("detections", "capteur, règle, revue"),
    ("publications", "cible, statut, relecture"),
    ("score_history", "score + politique"),
    ("lifecycle_events", "acteur, avant / après"),
    ("audit_logs", "append-only (trigger)"),
    ("reports", "synthèse quotidienne"),
]
for index, (table, note) in enumerate(EVIDENCE):
    y = 50.6 - index * 3.75
    ax.text(EVIDENCE_X + 1.8, y, table, ha="left", va="center", fontsize=6.9,
            fontweight="bold", color=INK, family="DejaVu Sans Mono", zorder=3)
    ax.text(EVIDENCE_X + 1.8, y - 1.55, note, ha="left", va="center",
            fontsize=6.1, color=GREY, zorder=3)
ax.text(EVIDENCE_X + 14.5, 13.6, "chaque étape laisse une trace horodatée",
        ha="center", va="center", fontsize=5.9, style="italic", color=GREY,
        zorder=3)

# ------------------------------------------------------------ arrows ------
for x in (33.9, 47.6):
    arrow(x, 53.4, x, 48.0)
arrow(FLOW_W / 2, 41.4, FLOW_W / 2, 34.8)
for x in (34.0, 50.6):
    arrow(x, 25.4, x, 19.7)
for y in (44.6, 30.0, 15.6):
    arrow(FLOW_W + 0.1, y, EVIDENCE_X - 0.1, y, dashed=True, color=GREY, lw=0.9)

fig.subplots_adjust(left=0.0, right=1.0, top=1.0, bottom=0.0)
OUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT, dpi=220, facecolor="white", bbox_inches="tight", pad_inches=0.06)
print(f"figure ecrite : {OUT} ({OUT.stat().st_size / 1024:.0f} Ko)")
