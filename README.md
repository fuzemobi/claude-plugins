# fuzemobi/claude-plugins

Public [Claude Code](https://claude.com/claude-code) plugin marketplace.

## Install

```
/plugin marketplace add DietrichGebert/ponytail   # needed by team-mode
/plugin marketplace add fuzemobi/claude-plugins
/plugin install doc-extract@fuzemobi-plugins
/plugin install carrier-tower-research@fuzemobi-plugins
/plugin install team-mode@fuzemobi-plugins
/plugin install fast-jev-compaction@fuzemobi-plugins
```

## Plugins

### team-mode

A config-driven multi-agent engineering team: research → plan → work → review → ship, run by a roster of voting specialist agents with domain-scoped vetoes, evidence standards, machine-verified done gates (a `DONE` vote is invalid without a green test-gate line in the transcript), structured context handoffs, and a GitHub-native paper trail (issues, labels, PRs, approval audit comments, tags). 16 slash commands + 2 skills, plus trajectory checks on every completion, ponytail-enforced KISS (a declared plugin dependency), and an optional code-graph atlas; all project specifics live in one team config — see [team-mode/README.md](team-mode/README.md) and the [example config](team-mode/examples/config.example.json).

### fast-jev-compaction

Replaces Claude Code's built-in compaction summary with verbatim pruning. When context fills up, TypeSafe's Jev model scores every tool call and tool result in one fast request: stale results are truncated to a short head plus a note, stale calls are dropped with their results, and everything kept stays word for word. User and assistant text is never removed or reworded, so file paths, exact errors and constraints survive compaction. It runs on `/compact` and automatically at 60% context, and falls back to the built-in summary when it can't cut at least 25%. Source: [fuzemobi/fast-jev-compaction](https://github.com/fuzemobi/fast-jev-compaction).

Setup (Claude Code 2.1.274+; function hooks are early access):

1. Add `"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1"` under `env` in `~/.claude/settings.json`.
2. `/plugin install fast-jev-compaction@fuzemobi-plugins`
3. Store your TypeSafe key as the plugin's sensitive option (kept out of `settings.json`): `echo '{"apiKey":"<key>"}' | claude plugin configure fast-jev-compaction@fuzemobi-plugins --values-stdin`, or set `TYPESAFE_API_KEY` in the environment.
4. Restart Claude Code or run `/reload-plugins`, then look for the `kept N/M messages` toast after a compaction.

Data note: each compaction sends message text and tool inputs (tool outputs reduced to one-line notes) to `api.typesafe.ai`. Disable it per project with `"enabledPlugins": {"fast-jev-compaction@fuzemobi-plugins": false}` in that repo's `.claude/settings.json`.

### carrier-tower-research

Build authoritative cell-tower master lists for any mobile carrier from an MCC/MNC, TADIG, or carrier name — FCC ULS/ASR/FAA/BDC/ECFS, international regulators (Ofcom, BNetzA, ACMA, …), and crowdsourced RF observations (OpenCelliD, CellMapper), merged in an explicit 11-level trust order with per-row provenance. Emits a 29-column CSV plus a reproducible methodology doc; includes bulk-pull, ASR-search, OpenCelliD, and merge scripts. See [carrier-tower-research/README.md](carrier-tower-research/README.md) for the full write-up.

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
