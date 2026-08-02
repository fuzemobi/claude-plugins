---
name: team-document
description: 'Document the current branch''s changes — refresh docstrings, update CHANGELOG, regenerate PROJECT_REFERENCE.md if API/CLI changed. Invoked automatically by `/team-ship` step 11, or manually when you want a doc pass without shipping.'
argument-hint: '[--auto] [--section api|cli|changelog|all]'
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, mcp__codegraph__codegraph_search, mcp__codegraph__codegraph_context]
model: sonnet
enabled: true
---

# /team-document

Per-branch documentation refresh. Used both inline during `/team-ship` (with `--auto`) and standalone when you want to document without shipping.

## When called

- **Automatically**: `/team-ship` step 11 invokes `/team-document --auto` right after merge + dev build. Ensures docs ship alongside code.
- **Manually**: during `/team-work`, you might run `/team-document` to catch up docs mid-flight, before calling completion vote.

## What it does

### 1. Compute the changed surface
```bash
git diff develop...HEAD --name-only
```

**Orientation first (B3_warm):** before rewriting docstrings or summarizing modules, run `cgdigest <dir> --reduce` (or `python3 ~/.claude/skills/codebase-digest/cgdigest.py --dir <path> --reduce`) on the changed directories. It returns cached skeleton+prose digests via Cerebras gpt-oss-120b — sub-second and nearly free on unchanged files — so you summarize from the digest instead of re-reading every file. Pull exact signatures from `codegraph_context` / Read for anything you document verbatim.

### 2. Decide which docs to refresh

| If the diff touches… | Refresh |
|---|---|
| Route/controller source (the surface `config.docGen.extractRoutes` reads) | `docs/PROJECT_REFERENCE.md` (API section) |
| CLI command source (the surface `config.docGen.cli` enumerates) | `docs/PROJECT_REFERENCE.md` (CLI section) |
| Any source file | `CHANGELOG.md` (add entry) |
| `docs/ARCHITECTURE.md` is referenced or a new module was added | Prompt user: hand-curation needed |
| Docstrings in changed functions | Should already be updated per `/team-work` step 3 — verify |

### 3. Run the refreshers

```bash
# For API/CLI surfaces
/team-sync-document

# For CHANGELOG — append entry for this PR's commits
git log develop..HEAD --oneline | while read line; do
    echo "- $line" >> CHANGELOG.md.pending
done
# Then merge into CHANGELOG.md under the new version section
```

### 4. Verify docstring discipline

For each changed function in the diff, confirm:
- It has a docstring.
- The docstring reflects the current behavior (not the pre-fix behavior).
- Any new parameters are documented.

If a function was changed and its docstring is empty or stale, flag it:

```
⚠ Docstring drift: `<changed-file>::<changed-function>()` (L42)
  — behavior changed in this PR but docstring was not updated.
  Fix before completion vote (the DOCUMENT → CODE → TEST → COMMIT discipline in `<config.nonNegotiables>`).
```

### 5. Commit the doc changes

```bash
git add docs/ CHANGELOG.md
git commit -m "docs: refresh reference + changelog for #<issue> (vX.Y.Z)"
```

This commit is separate from the code commits — keeps the diff clean for review.

## Modes

### `--auto` (used by `/team-ship`)

- Non-interactive.
- Runs `/team-sync-document` always (covers API + CLI).
- Appends a CHANGELOG entry using the PR title + issue number.
- If docstring drift is detected, **does not block ship** but leaves a warning in the output.

### Manual (default)

- Interactive.
- Asks before committing.
- Blocks completion vote in `/team-work` if docstring drift is detected.

## Docstring drift detection

Heuristic: if a function's AST changed between `develop` and `HEAD` but its docstring didn't, flag it. Can be overridden on a per-function basis by adding `# doc: verified-manual` as the line before `def`.

## Non-negotiables

Referenced by name/domain — read `<config.nonNegotiables>` for the project's exact rules and numbering.

- **DOCUMENT → CODE → TEST → COMMIT**: this command enforces that discipline.
- **Docs ride with the commit**: doc updates ride inside the code commit, not separate — except for PROJECT_REFERENCE.md + CHANGELOG which can be a follow-up commit because they aggregate across the whole branch.
