"""Render abstract.pdf from abstract.txt.

Presentation only: this never recomputes a result. It reads the frozen abstract
text, so the PDF cannot drift from the submitted words. Requires the optional
`docs` extra (`uv sync --extra docs`).

    python make_abstract_pdf.py
"""
from pathlib import Path
import re
import sys

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)

HERE = Path(__file__).resolve().parent
SRC = HERE / "abstract.txt"
OUT = HERE / "abstract.pdf"

TITLE = "Ratings Are Not Forecasts: Accounting, Calibration, and Information Timing in NBA Player-Impact Forecasting"
AUTHOR = "Geoffrey Hadfield"
AFFIL = "World Model Sports LLC"
REPO = "https://github.com/ghadfield32/ssac27-ratings-are-not-forecasts"

if not SRC.exists():
    sys.exit(f"missing {SRC.name}")

lines = SRC.read_text(encoding="utf-8").splitlines()

# Section paragraphs are the lines beginning with the four section labels.
SECTIONS = ("Introduction.", "Methods.", "Results.", "Conclusion.")
body = [l for l in lines if l.strip().startswith(SECTIONS)]

# Table rows: markdown pipe rows.
rows = [l for l in lines if l.strip().startswith("|")]
table_data = []
for r in rows:
    cells = [c.strip() for c in r.strip().strip("|").split("|")]
    if all(set(c) <= set(":-") and c for c in cells):
        continue  # alignment row
    table_data.append(cells)

# The trailing note is the paragraph after the table that is not a section.
note = None
for i, l in enumerate(lines):
    s = l.strip()
    if s and not s.startswith(SECTIONS) and not s.startswith("|") \
            and not s.startswith("Table 1") and s != TITLE:
        note = s

styles = getSampleStyleSheet()
h = ParagraphStyle("h", parent=styles["Heading1"], fontSize=12.5, leading=15,
                   spaceAfter=5, textColor=colors.HexColor("#111111"))
sub = ParagraphStyle("sub", parent=styles["Normal"], fontSize=9.2, leading=12,
                     alignment=1, spaceAfter=2, textColor=colors.HexColor("#333333"))
p = ParagraphStyle("p", parent=styles["Normal"], fontSize=9.3, leading=12.6,
                   spaceAfter=5.5, alignment=4)
tnote = ParagraphStyle("tn", parent=styles["Normal"], fontSize=8.2, leading=10.5,
                       spaceBefore=3, textColor=colors.HexColor("#444444"))
link = ParagraphStyle("link", parent=styles["Normal"], fontSize=8.2, leading=10.5,
                      spaceBefore=7, textColor=colors.HexColor("#1a4d8f"))

doc = SimpleDocTemplate(str(OUT), pagesize=LETTER,
                        leftMargin=0.8 * inch, rightMargin=0.8 * inch,
                        topMargin=0.6 * inch, bottomMargin=0.55 * inch,
                        title=TITLE, author=AUTHOR)

story = [
    Paragraph(TITLE, h),
    Paragraph(f"{AUTHOR} &nbsp;&middot;&nbsp; {AFFIL}", sub),
    Spacer(1, 7),
]
for para in body:
    label, _, rest = para.partition(" ")
    story.append(Paragraph(f"<b>{label}</b> {rest}", p))

if table_data:
    t = Table(table_data, hAlign="LEFT", colWidths=[1.7 * inch, 1.1 * inch,
                                                    1.45 * inch, 1.75 * inch])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.4),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#333333")),
        ("LINEABOVE", (0, -1), (-1, -1), 0.6, colors.HexColor("#333333")),
        ("ROWBACKGROUNDS", (0, 1), (-1, 1), [colors.HexColor("#fafafa")]),
        ("TOPPADDING", (0, 0), (-1, -1), 2.6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
    ]))
    story.append(Spacer(1, 3))
    story.append(t)

if note:
    story.append(Paragraph(note, tnote))
story.append(Paragraph(f"Supporting repository: {REPO}", link))

doc.build(story)
print(f"wrote {OUT.name} ({OUT.stat().st_size} bytes) from {SRC.name}")
