#!/usr/bin/env python3
"""Structural PDF extraction: headings, tables, form fields, reading order.

Usage:
  pdf_structure.py file.pdf            # structured Markdown to stdout
  pdf_structure.py --json file.pdf     # tagged elements as JSON
  pdf_structure.py --triage file.pdf   # per-page classification only
  pdf_structure.py --selftest          # build a tiny PDF in memory and verify
"""
import contextlib
import json
import re
import statistics
import sys

try:
    import pymupdf as fitz  # PyMuPDF >= 1.24 canonical name (no deprecation banner)
except ImportError:
    import fitz  # PyMuPDF, older releases


def find_tables_quiet(page):
    """page.find_tables(), with PyMuPDF's advisory prints kept off stdout.

    Newer PyMuPDF versions print upgrade hints to stdout, which corrupts
    machine-read output (--json). Route them to stderr instead.
    """
    with contextlib.redirect_stdout(sys.stderr):
        return page.find_tables()

SCAN_TEXT_THRESHOLD = 20  # chars; below this + has images -> treat page as scanned
HEADING_RATIO = 1.15      # span size > body_size * ratio -> heading
COLUMN_SPLIT = re.compile(r"\s{2,}")  # 2+ spaces = column gap in layout-sorted text


def body_font_size(doc: fitz.Document) -> float:
    """Most common span size across the doc = body text size."""
    sizes = []
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                sizes.extend(round(s["size"], 1) for s in line["spans"])
    return statistics.mode(sizes) if sizes else 12.0


def table_to_markdown(rows: list) -> str:
    def clean(c):
        return (c or "").replace("\n", " ").strip()
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [list(r) + [""] * (width - len(r)) for r in rows]
    out = ["| " + " | ".join(clean(c) for c in rows[0]) + " |",
           "|" + "---|" * width]
    out += ["| " + " | ".join(clean(c) for c in r) + " |" for r in rows[1:]]
    return "\n".join(out)


def borderless_tables(page) -> list:
    """Fallback for tables drawn without ruling lines (bank/brokerage statements).

    find_tables() needs cell borders; statement-style PDFs rarely draw them, and
    without this fallback their tables degrade to scrambled paragraphs — the exact
    failure mode this skill exists to prevent. Columns still appear as runs of 2+
    spaces in layout-sorted text, and consecutive multi-column lines form a table.
    Emits the same element shape as the bordered path, plus `rows` (cells as data).
    """
    elements = []
    lines = page.get_text("text", sort=True).splitlines()
    block = []

    def flush():
        nonlocal block
        if not block:
            return
        multi = [r for r in block if len(r) >= 2]
        if len(multi) >= 2:
            elements.append({"type": "table", "rows": block,
                             "text": table_to_markdown(block)})
        else:
            for r in block:
                txt = " ".join(r)
                if txt:
                    elements.append({"type": "paragraph", "text": txt})
        block = []

    for ln in lines:
        cells = [c.strip() for c in COLUMN_SPLIT.split(ln.strip()) if c.strip()]
        if not cells:
            flush()
        elif len(cells) >= 2 or block:
            block.append(cells)
        else:
            elements.append({"type": "paragraph", "text": cells[0]})
    flush()
    return elements


def extract(doc: fitz.Document) -> list:
    """Return tagged elements: heading | paragraph | table | form_field | scanned_page."""
    elements = []
    body = body_font_size(doc)

    for page in doc:
        pno = page.number + 1

        for w in page.widgets() or []:
            elements.append({"page": pno, "type": "form_field",
                             "name": w.field_name, "value": w.field_value})

        text = page.get_text().strip()
        if len(text) < SCAN_TEXT_THRESHOLD and page.get_images():
            elements.append({"page": pno, "type": "scanned_page",
                             "text": f"[SCANNED PAGE {pno} — no text layer]"})
            continue

        tables = find_tables_quiet(page)
        table_bboxes = [fitz.Rect(t.bbox) for t in tables]
        for t in tables:
            rows = t.extract()
            elements.append({"page": pno, "type": "table",
                             "rows": rows, "text": table_to_markdown(rows)})

        if not table_bboxes:
            # No bordered tables detected — try the borderless (whitespace-column)
            # fallback. If it finds table structure, it replaces the block dump
            # for this page; otherwise fall through to the normal path.
            fb = borderless_tables(page)
            if any(e["type"] == "table" for e in fb):
                for e in fb:
                    e["page"] = pno
                elements.extend(fb)
                continue

        # sort=True gives reading order (top-down, left-right within columns)
        for block in page.get_text("dict", sort=True)["blocks"]:
            if block.get("type") != 0:
                continue
            r = fitz.Rect(block["bbox"])
            if any(r.intersects(tb) for tb in table_bboxes):
                continue  # text already captured inside a table
            spans = [s for ln in block["lines"] for s in ln["spans"]]
            btext = " ".join(s["text"] for s in spans).strip()
            if not btext:
                continue
            max_size = max(s["size"] for s in spans)
            if max_size > body * HEADING_RATIO and len(btext) < 200:
                level = 1 if max_size > body * 1.6 else 2
                elements.append({"page": pno, "type": "heading",
                                 "level": level, "text": btext})
            else:
                elements.append({"page": pno, "type": "paragraph", "text": btext})
    return elements


def to_markdown(elements: list) -> str:
    out, cur_page = [], None
    fields = [e for e in elements if e["type"] == "form_field"]
    if fields:
        out.append("## Form fields\n\n| Field | Value |\n|---|---|")
        out += [f"| {f['name']} | {f['value'] or ''} |" for f in fields]
        out.append("")
    for e in elements:
        if e["type"] == "form_field":
            continue
        if e["page"] != cur_page:
            cur_page = e["page"]
            out.append(f"\n<!-- page {cur_page} -->\n")
        if e["type"] == "heading":
            out.append("#" * e["level"] + " " + e["text"] + "\n")
        else:
            out.append(e["text"] + "\n")
    return "\n".join(out)


def triage(doc: fitz.Document) -> str:
    lines = []
    for page in doc:
        text = page.get_text().strip()
        scanned = len(text) < SCAN_TEXT_THRESHOLD and bool(page.get_images())
        n_tables = len(find_tables_quiet(page).tables)
        n_fields = len(list(page.widgets() or []))
        lines.append(f"page {page.number + 1}: "
                     f"{'SCANNED (no text layer)' if scanned else f'text ({len(text)} chars)'}"
                     f", tables={n_tables}, form_fields={n_fields}")
    return "\n".join(lines)


def selftest():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 80), "Quarterly Report", fontsize=24)
    page.insert_text((72, 120), "Revenue grew this quarter.", fontsize=11)
    # draw a 2x2 table with cell borders so find_tables can see it
    for r in (fitz.Rect(72, 150, 200, 175), fitz.Rect(200, 150, 328, 175),
              fitz.Rect(72, 175, 200, 200), fitz.Rect(200, 175, 328, 200)):
        page.draw_rect(r)
    page.insert_text((76, 167), "Region", fontsize=11)
    page.insert_text((204, 167), "Sales", fontsize=11)
    page.insert_text((76, 192), "West", fontsize=11)
    page.insert_text((204, 192), "500", fontsize=11)

    els = extract(doc)
    types = {e["type"] for e in els}
    assert "heading" in types, f"no heading detected: {els}"
    assert any(e["type"] == "heading" and "Quarterly" in e["text"] for e in els)
    assert "table" in types, f"no table detected: {els}"
    table = next(e for e in els if e["type"] == "table")
    assert "West" in table["text"] and "500" in table["text"], table["text"]
    md = to_markdown(els)
    assert "# Quarterly Report" in md and "| West | 500 |" in md
    print("selftest OK")


def main():
    args = sys.argv[1:]
    if "--selftest" in args:
        return selftest()
    mode = "md"
    if "--json" in args:
        mode, args = "json", [a for a in args if a != "--json"]
    if "--triage" in args:
        mode, args = "triage", [a for a in args if a != "--triage"]
    if not args:
        sys.exit(__doc__)
    doc = fitz.open(args[0])
    if mode == "triage":
        print(triage(doc))
    elif mode == "json":
        print(json.dumps(extract(doc), indent=2))
    else:
        print(to_markdown(extract(doc)))


if __name__ == "__main__":
    main()
