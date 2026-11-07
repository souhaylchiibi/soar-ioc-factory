"""Convert a Markdown file to Word (.docx) — minimal but honest converter.

Supports: #/##/### headings, ``` code fences (monospace), - bullets,
| tables |, **bold**, `inline code`, plain paragraphs.

Usage: python scripts/md_to_docx.py <input.md> <output.docx>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor


def add_inline(paragraph, text: str) -> None:
    """Render **bold** and `code` inline markers."""
    pattern = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")
    pos = 0
    for match in pattern.finditer(text):
        if match.start() > pos:
            paragraph.add_run(text[pos:match.start()])
        token = match.group(0)
        if token.startswith("**"):
            run = paragraph.add_run(token[2:-2])
            run.bold = True
        else:
            run = paragraph.add_run(token[1:-1])
            run.font.name = "Consolas"
            run.font.color.rgb = RGBColor(0x0E, 0x5A, 0x8A)
        pos = match.end()
    if pos < len(text):
        paragraph.add_run(text[pos:])


def convert(md_path: Path, docx_path: Path) -> tuple[int, int]:
    lines = md_path.read_text(encoding="utf-8").splitlines()
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)

    in_code = False
    code_buf: list[str] = []
    in_table = False
    headings = paragraphs = 0

    def flush_code() -> None:
        p = doc.add_paragraph()
        run = p.add_run("\n".join(code_buf))
        run.font.name = "Consolas"
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x1F, 0x3D, 0x66)
        p.paragraph_format.space_after = Pt(8)

    def flush_table(rows: list[list[str]]) -> None:
        if not rows:
            return
        t = doc.add_table(rows=len(rows), cols=len(rows[0]))
        t.style = "Light Grid Accent 1"
        for r_i, row in enumerate(rows):
            for c_i, cell in enumerate(row[: len(rows[0])]):
                t.rows[r_i].cells[c_i].text = cell.strip()
                for p in t.rows[r_i].cells[c_i].paragraphs:
                    for run in p.runs:
                        run.font.size = Pt(9)
                        if r_i == 0:
                            run.bold = True
        doc.add_paragraph()

    table_rows: list[list[str]] = []

    for raw in lines:
        line = raw.rstrip()

        # code fences
        if line.startswith("```"):
            if in_code:
                flush_code()
                code_buf = []
                in_code = False
            else:
                in_table, table_rows = False, []
                in_code = True
            continue
        if in_code:
            code_buf.append(raw)
            continue

        # tables
        if line.startswith("|") and line.endswith("|") and line.count("|") >= 2:
            cells = [c for c in line.strip("|").split("|")]
            if all(re.fullmatch(r"[\s:|-]+", c) for c in cells):   # separator row
                continue
            table_rows.append(cells)
            in_table = True
            continue
        if in_table:
            flush_table(table_rows)
            table_rows = []
            in_table = False

        # headings
        m = re.match(r"^(#{1,3})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            doc.add_heading(m.group(2), level=min(level, 3))
            headings += 1
            continue

        # bullets
        if line.startswith("- "):
            p = doc.add_paragraph(style="List Bullet")
            add_inline(p, line[2:])
            paragraphs += 1
            continue

        # numbered steps kept as plain paragraphs (their numbers matter)
        if not line.strip():
            continue

        p = doc.add_paragraph()
        add_inline(p, line)
        paragraphs += 1

    if table_rows:
        flush_table(table_rows)
    if code_buf:
        flush_code()

    docx_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(docx_path))
    return headings, paragraphs


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    md = Path(sys.argv[1])
    out = Path(sys.argv[2])
    if not md.exists():
        print(f"introuvable: {md}")
        return 1
    headings, paragraphs = convert(md, out)
    print(f"converti: {out}")
    print(f"  titres: {headings} | paragraphes/listes: {paragraphs}")
    print(f"  taille: {round(out.stat().st_size / 1024)} Ko")
    return 0


if __name__ == "__main__":
    sys.exit(main())
