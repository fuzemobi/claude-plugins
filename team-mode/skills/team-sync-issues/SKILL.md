---
name: team-sync-issues
description: 'Use when the user wants to sync the project''s open-issues tracking spreadsheet with GitHub — typically `./tmp/_OPEN_ISSUES.xlsx`. Triggers on "/team-sync-issues", "sync issues", "refresh the issues spreadsheet", or any reference to the open-issues tracker being stale. GH is authoritative for Issue #, Title, Labels, URL, Status, and dates; the spreadsheet is authoritative for Priority, Type, and Notes.'
---

# team-sync-issues

## What this skill does

Keeps `<project>/tmp/_OPEN_ISSUES.xlsx` in sync with GitHub. Run it at the start of a planning session, after a bulk of issue activity, or whenever the spreadsheet feels stale.

## Source-of-truth split

| Field         | Authoritative source | How it's handled                           |
|---------------|----------------------|--------------------------------------------|
| Issue #       | GitHub               | Never changed by a human                   |
| Title         | GitHub               | Overwritten on sync                        |
| Labels        | GitHub               | Overwritten on sync                        |
| URL           | GitHub               | Overwritten on sync                        |
| Status        | GitHub (derived)     | Derived from state + labels; overwritten   |
| created_date  | GitHub               | Set once on add                            |
| modified_date | GitHub               | Overwritten on sync                        |
| Priority      | **Human** (xlsx)     | Preserved; auto-inferred only for NEW rows |
| Type          | **Human** (xlsx)     | Preserved; auto-inferred only for NEW rows |
| Notes         | **Human** (xlsx)     | Preserved forever                          |

## How to invoke

From Claude Code, use the slash command:
```
/team-sync-issues                # default: ./tmp/_OPEN_ISSUES.xlsx, current repo
/team-sync-issues --dry-run      # show the diff, don't write
/team-sync-issues --xlsx PATH    # custom path
/team-sync-issues --repo O/R     # explicit repo (otherwise derived from git remote)
```

The command runs the script at `${CLAUDE_PLUGIN_ROOT}/skills/team-sync-issues/sync_issues.py`.

## Prerequisites

1. `gh` CLI installed and authenticated (`gh auth status` succeeds).
2. Python 3 with `openpyxl` installed (this script is Python + openpyxl regardless of the project's own stack).
3. Running from a git repo or passing `--repo OWNER/REPO`.
4. NON_NEGOTIABLES loaded — no sensitive/PII data, no secrets in issue bodies that would land in the sheet.

## Inference rules

### Type (from title prefix first, then labels)

| Signal                        | → Type   |
|-------------------------------|----------|
| Title prefix `fix:`           | BUG      |
| Title prefix `feat:` `feature:` | FEATURE |
| Title prefix `chore:` `refactor:` `test:` `perf:` `ci:` `build:` | CHORE |
| Title prefix `docs:` `doc:`   | DOCS     |
| Title prefix `data:`          | DATA     |
| Label `BUG`                   | BUG      |
| Label `ENHANCEMENT` `FEATURE` | FEATURE  |
| Label `DOCUMENTATION` `DOCS`  | DOCS     |
| Label `data-quality` `data-mapping` | DATA |
| Fallback                      | CHORE    |

### Priority (from labels)

| Label                              | → Priority    |
|------------------------------------|---------------|
| `URGENT` `high-priority` `P0` `P1` | 1 - HIGH      |
| `low-priority` `P3`                | 3 - LOW       |
| `medium-priority` `P2` (or none)   | 2 - MEDIUM    |

### Status (from state + labels)

| Signal                         | → Status       |
|--------------------------------|----------------|
| GH state `closed`              | CLOSED         |
| Label `in-progress`            | IN PROGRESS    |
| Label `in-review`              | IN REVIEW      |
| Label `testing`                | TESTING        |
| Label `pr-follow-up`           | PR FOLLOW-UP   |
| Label `blocked`                | BLOCKED        |
| Label `ready` or none of above | READY          |

## Sync behavior

On every run:

1. **Backup** the current xlsx to `tmp/backups/_OPEN_ISSUES_<UTC-timestamp>.xlsx`.
2. **Fetch** open + recently-closed GH issues via `gh issue list`.
3. **Diff**:
   - `ADD` — in GH, not in xlsx (open state) → append row, auto-infer Priority/Type/Status.
   - `UPDATE` — in both → overwrite volatile fields; keep Priority, Type, Notes.
   - `CLOSE` — in xlsx, closed in GH → move to a "Recently Closed" sheet (kept in same workbook).
   - `MISSING` — in xlsx, not in GH at all (rare, probably deleted) → move to Recently Closed with Status = `MISSING`.
   - `UNCHANGED` — identical → no write.
4. **Write** the workbook (unless `--dry-run`).
5. **Report** the diff summary to stdout.

## Format preservation

Per the xlsx skill: "Never impose standardized formatting on files with established patterns." The script:
- Updates cells in place (preserves font, column widths, row heights).
- Does NOT add styling to existing files.
- If the file is missing and must be created from scratch, applies reasonable defaults: Calibri 11, bold header, freeze row 1, auto-filter.

## What to do when the script reports something weird

- **Auth error from `gh`**: run `gh auth login` — the script stops cleanly.
- **Many closed issues moving at once**: probably a cleanup sweep — verify the Recently Closed sheet is what you expect before re-running.
- **MISSING rows**: someone deleted issues in GH. Check the GH audit log and decide whether to restore or leave in Recently Closed.
- **Conflict** (GH labels contradict xlsx Priority): script keeps xlsx Priority. If GH is the source of truth for priority for your workflow, edit in GH and resync.

## Non-negotiables relevant to this skill

Referenced by name/domain — each project's `NON_NEGOTIABLES.md` owns its own numbering.

- **Sensitive-data rule** — the script does not echo issue-body content to stdout beyond titles/labels. Sensitive/PII data in an issue body will NOT appear in the sheet (Notes is human-only).
- **Secrets rule** — the script does not read secrets from anywhere. The `gh` CLI handles its own auth.
- Output artifacts (the xlsx, the backup) live inside the project and should not be committed if `tmp/` is gitignored.
