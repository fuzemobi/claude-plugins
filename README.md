# fuzemobi/claude-plugins

Public [Claude Code](https://claude.com/claude-code) plugin marketplace.

## Install

```
/plugin marketplace add fuzemobi/claude-plugins
/plugin install doc-extract@fuzemobi-plugins
```

## Plugins

### doc-extract

Structural extraction from any document — structure (headings, tables, form fields, reading order), not raw character dumps. Naive extraction copies characters in draw order: it merges table rows, scrambles multi-column text, returns nothing for scanned pages, and misses PDF form values stored separately from visible text. This skill fixes that.

One entry point, auto-routed by extension:

| Format | Route | What's preserved |
|---|---|---|
| .pdf | PyMuPDF | headings (font-size), GFM tables, form field values, reading order, scanned-page flags; `--json`, `--triage` |
| .docx .html .epub .rtf .odt | pandoc → GFM (stdlib docx fallback) | native structure |
| .xlsx | openpyxl | one GFM table per sheet, computed values |
| .pptx .csv .tsv | stdlib only | slide text / GFM table |
| .txt .md .json | passthrough | already machine-readable |

```bash
python3 skills/doc-extract/scripts/extract.py <file>          # structured Markdown
python3 skills/doc-extract/scripts/extract.py --json f.pdf    # tagged elements for RAG
python3 skills/doc-extract/scripts/pdf_structure.py --triage f.pdf  # scanned? forms? tables?
```

Dependencies: `pymupdf` for PDFs, `pandoc` + `openpyxl` recommended; everything else is Python stdlib. Both scripts include `--selftest`.

## License

MIT
