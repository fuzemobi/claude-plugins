---
name: doc-extract
description: "Structural extraction from any document — PDF, DOCX, XLSX, PPTX, CSV, HTML, EPUB, TXT — structure (headings, tables, form fields, reading order), not just characters. Use whenever asked to read, extract, parse, summarize, or convert a document, pull tables to CSV/Markdown, handle scanned documents, or read PDF form values. Triggers on: 'extract this pdf/docx/spreadsheet', 'read this document', 'convert to markdown', 'pull the tables', 'scanned pdf', 'OCR', 'form fields', 'parse this file'."
---

# Doc-Extract Skill

Naive extraction copies characters in draw order. It silently merges table rows, scrambles multi-column text, returns nothing for scanned pages, and misses form-field values stored separately from visible text. This skill extracts **structure** — from any document type, via one entry point.

## One command for any document

```bash
python3 <this-skill-dir>/scripts/extract.py <file>
```

`<this-skill-dir>` = the directory containing this SKILL.md (in Claude Code: `~/.claude/skills/doc-extract`; in Desktop/Cowork the skill is unpacked elsewhere — resolve the path relative to this file). If PyMuPDF or pandoc is missing in the current environment, the script says so and degrades gracefully (docx falls back to a dependency-free extractor).

Auto-routes by extension and emits structured Markdown on stdout (chunk-ready):

| Format | Route | What's preserved |
|---|---|---|
| .pdf | PyMuPDF (`pdf_structure.py`) | headings (font-size), GFM tables, form field values, reading order, scanned-page flags |
| .docx .html .epub .rtf .odt | `pandoc -t gfm` | native structure — these formats already store it |
| .xlsx | openpyxl | one GFM table per sheet, computed values |
| .pptx | stdlib zip/XML | text per slide, slide order |
| .csv .tsv | stdlib csv | GFM table |
| .txt .md .json .log | passthrough | already machine-readable |
| .doc .xls .ppt | refused with convert hint | legacy binary — convert to the x-format first |

`--json` (PDF only) emits tagged elements `{page, type, text}`, `type ∈ heading|paragraph|table|form_field|scanned_page`. Sheets/CSVs cap at 500 rows and **announce** truncation.

## Rule zero for PDFs: triage before trusting

```bash
python3 <this-skill-dir>/scripts/pdf_structure.py --triage file.pdf
```

Reports per-page: text layer vs scanned (image-only), table count, form-field count. Never conclude "the document is empty" from a text dump — a scanned page has no characters to dump.

## When NOT to use the script

- **Answering questions about a short PDF (≤20 pages)**: Claude's Read tool renders pages visually — tables, columns, stamps, and scans all just work. Laziest correct option.
- **Scanned pages / bulk OCR**: no OCR stack installed (`ocrmypdf`/`tesseract` absent). For a few pages, Read them visually and transcribe — Claude *is* the OCR. For bulk, ask before installing `ocrmypdf` (CLAUDE.md §6.1).
- **Cell-level spreadsheet surgery or doc styles**: drop to `openpyxl` / `python-docx` directly.

## Failure modes this skill exists to prevent

| Symptom | Cause | Fix |
|---|---|---|
| "The PDF is empty" | Scanned page, no text layer | Triage first; Read pages visually |
| Numbers in wrong rows | Char-order dump of a table | `find_tables()` via extract.py, or Read visually |
| Garbled interleaved sentences | Multi-column read in draw order | extract.py sorts blocks in reading order |
| Form comes back blank | Values live in AcroForm fields, not page text | extract.py dumps widget name→value |
| Ad-hoc regex parsing of .docx XML | Forgot pandoc exists | pandoc route |
| Half a spreadsheet silently missing | Unannounced truncation | 500-row cap is always announced |

## Don't

- Don't run `pdftotext` on anything with tables or columns and treat the output as truth (fine for quick full-text grep of simple prose PDFs).
- Don't conclude a document lacks signatures, stamps, or images from a text dump — those are non-text elements; check visually.
- Don't install new extraction libraries; the installed set (fitz, pandoc, openpyxl, python-docx, pdftotext, stdlib) covers every supported format.

## The bottom line

Structure before retrieval. If the extraction step loses the table rows, nothing downstream gets them back — for PDFs, spreadsheets, decks, or anything else.
