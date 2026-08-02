---
name: team-sync-document
description: 'Generate or refresh the project reference document (PROJECT_REFERENCE.md) by extracting API routes from source and CLI commands from the project''s CLI help output. The route extractor and CLI command come from the team config, so it works on any stack. Preserves hand-written sections between `<!-- generated -->` markers. Run after any PR that changes API surfaces, CLI commands, or architecture.'
argument-hint: '[--dry-run] [--section api|cli|stats|all] [--out PATH]'
allowed-tools: [Bash, Read]
model: haiku
enabled: true
---

# /team-sync-document

Generates/refreshes `PROJECT_REFERENCE.md` — the standing reference that lists every API endpoint, every CLI command, and points to architecture docs. Calls `${CLAUDE_PLUGIN_ROOT}/scripts/sync_document.py`. The route extractor (`config.docGen.extractRoutes`), CLI command (`config.docGen.cli`), version source (`config.versionSource`), and project name (`config.name`) are all read from the team config — nothing about the stack is hardcoded.

## Usage

```
/team-sync-document                         # refresh everything (stats + api + cli)
/team-sync-document --dry-run               # preview without writing
/team-sync-document --section api           # only API section
/team-sync-document --section cli           # only CLI section
/team-sync-document --out docs/REFERENCE.md # custom output path
```

## Invocation (exact command Claude Code should run)

From the project root:

```bash
if [ -f venv/bin/activate ]; then
    source venv/bin/activate
elif [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi

python "${CLAUDE_PLUGIN_ROOT}/scripts/sync_document.py" "$@"
```

The script runs `config.docGen.cli` for CLI extraction, so that CLI must be on PATH — activate the venv (or whatever provides the CLI) first.

## What it extracts

### API surfaces (extractor per `config.docGen.extractRoutes`)

- **`flask`** — AST-based: every `Blueprint(...)` assignment and `@<bp>.route(...)` decorator under the scan roots; method list, path, handler function, first line of docstring, file:line.
- **`laravel`** — regex-based: every `Route::<verb>(...)` / `Route::match(...)` in `routes/*.php`, grouped by file; method, path, handler (`Controller@method`), file:line.
- **`express`** — stubbed (returns nothing yet).
- **`none`** — API section left empty.

### CLI commands (from `config.docGen.cli` help output)

- Every command listed by the configured CLI help invocation (e.g. `mycli --help`, `php artisan list`)
- Grouped by the sections the help output declares
- Command name + one-line description

## Preservation rules

The generated sections are wrapped in HTML comments:

```markdown
<!-- generated:START api -->
... (auto-regenerated content) ...
<!-- generated:END api -->
```

**Anything outside these markers is hand-written and preserved across runs.** The script only overwrites what's between the markers. New template sections (on first run, no file exists) include placeholder markers that you can fill with hand-written content.

The Architecture, Critical Flows, and Non-Negotiables sections are hand-curated — the script never overwrites them.

When you DO refresh those hand-written prose sections (e.g. a PR reshaped a module), orient with `cgdigest <dir> --reduce` (or `python3 ~/.claude/skills/codebase-digest/cgdigest.py --dir <path> --reduce`) first — it returns cached skeleton+prose digests via Cerebras gpt-oss-120b, sub-second on unchanged files, so you summarize the changed area from the digest instead of re-reading it. The generated route/CLI blocks stay script-extracted; cgdigest is only for the prose.

## When to run this

- **After any PR that changes API surfaces** (new route, new blueprint, removed endpoint).
- **After any PR that adds or removes CLI commands.**
- **Automatically at the end of `/team-ship`** (step 11 — the `--auto` flag is deprecated; this command replaces it).
- **Periodically**, even when nothing changed — catches drift (e.g., routes added manually, untracked CLIs).

## Output example

```
project root: /path/to/project
project name: <config.name>
output:       /path/to/project/PROJECT_REFERENCE.md
section:      all
routes:       laravel
cli:          php artisan list

scanning…
  20 route groups (52 routes)
  41 CLI commands

✓ wrote /path/to/project/PROJECT_REFERENCE.md (8432 bytes)
```

## When to commit the result

The generated file lives at `PROJECT_REFERENCE.md` — in git, not in `.claude/`. Commit the update as part of the same PR that changed the underlying API/CLI:

```bash
/team-sync-document
git add PROJECT_REFERENCE.md
git commit -m "docs: refresh PROJECT_REFERENCE for vX.Y.Z"
```

Or, if called automatically at end of `/team-ship`, it lands on `develop` via a follow-up commit `docs: refresh project reference for vX.Y.Z`.

## Non-negotiables

Referenced by name/domain — each project's `NON_NEGOTIABLES.md` owns its own numbering.

- **Sensitive-data rule**: script does not emit sensitive/PII data — only route paths, handler names, and CLI command descriptions from docstrings/help text.
- **Secrets rule**: no secrets handled. Reads source files and runs the configured CLI help command.
- **Test-integrity rule**: no tests modified or disabled. Pure documentation generation.
