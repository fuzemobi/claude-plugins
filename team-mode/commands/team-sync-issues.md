---
name: team-sync-issues
description: 'Sync `./tmp/_OPEN_ISSUES.xlsx` with the current GitHub repo''s issues. GH is authoritative for title/labels/URL/status/dates; the spreadsheet preserves human-entered Priority, Type, and Notes. Backups are automatic. Closed issues move to a "Recently Closed" sheet.'
argument-hint: '[--dry-run] [--xlsx PATH] [--repo OWNER/REPO]'
allowed-tools: [Bash, Read]
model: haiku
enabled: true
---

# /team-sync-issues

Syncs the project's issue-tracking spreadsheet with GitHub. Calls `${CLAUDE_PLUGIN_ROOT}/skills/team-sync-issues/sync_issues.py`.

## Usage

```
/team-sync-issues                   # default: ./tmp/_OPEN_ISSUES.xlsx, derive repo from git remote
/team-sync-issues --dry-run         # show diff, write nothing
/team-sync-issues --xlsx tmp/ISSUES_2026Q2.xlsx
/team-sync-issues --repo OWNER/REPO
```

## Before first use in a project

Verify:
1. `gh auth status` succeeds (otherwise `gh auth login`).
2. The project has a Python venv with openpyxl installed, OR openpyxl is in the active python. (This script is Python + openpyxl regardless of the project's own stack.)

## How to invoke (exact command Claude Code should run)

From the project root:

```bash
# Activate whichever venv exists (`venv/` or `.venv/`)
if [ -f venv/bin/activate ]; then
    source venv/bin/activate
elif [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi

python "${CLAUDE_PLUGIN_ROOT}/skills/team-sync-issues/sync_issues.py" "$@"
```

Pass through all user-supplied args.

## Recommended usage pattern

**Always run `--dry-run` first** if it's been a while since the last sync, or if you suspect bulk changes:

```
/team-sync-issues --dry-run
```

Review the ADD / UPDATE / CLOSE / MISSING counts. If they look reasonable, run without `--dry-run`:

```
/team-sync-issues
```

A timestamped backup is written to `tmp/backups/_OPEN_ISSUES_<UTC-timestamp>.xlsx` before any modification — no dry-run needed for safety, just for confidence.

## What gets preserved across syncs

- **Priority** column (only auto-inferred for new rows)
- **Type** column (only auto-inferred for new rows)
- **Notes** column (never overwritten)
- **Sheet formatting**: column widths, fonts, freeze panes, auto-filter — the script updates cells in place rather than rewriting rows, so existing formatting carries forward

## What gets overwritten on every sync

- Title, Labels, URL
- Status (derived from GH labels + open/closed state)
- modified_date

## Output

The script prints a summary like:

```
[DRY-RUN] Sync summary
============================================================
  ADD (new in GH):            5
  UPDATE (fields changed):   12
  CLOSE (closed in GH):       3
  MISSING (removed in GH):    0
  UNCHANGED:                 22

--- ADD ---
  #443: feat: add pagination to the search endpoint
  ...
--- UPDATE ---
  ...
--- CLOSE ---
  ...
```

## When to run this

- Start of a planning session or `/team-status` check.
- After a sprint's worth of GH activity.
- Before `/team-start` on an issue, to confirm the xlsx reflects reality.
- After closing a batch of issues in GH, to move them to "Recently Closed."

## Non-negotiables

Referenced by name/domain — each project's `NON_NEGOTIABLES.md` owns its own numbering.

- **Sensitive-data rule** — script does not put issue body content into the sheet, only titles and labels. Any sensitive/PII data in a body will NOT land in the xlsx.
- **Secrets rule** — no secrets are handled by this script; `gh` CLI manages its own auth.
- **Read-only-scope rule** — script only touches the xlsx; it never modifies GH issues, creates branches, or merges anything. Safe to run as often as you like.

## Full documentation

`${CLAUDE_PLUGIN_ROOT}/skills/team-sync-issues/SKILL.md` — including the Type / Priority / Status inference tables.
