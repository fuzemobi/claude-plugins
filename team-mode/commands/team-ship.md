---
name: team-ship
description: 'Finalize and ship a completed branch — version bump, PR against develop, team code review, user-approved merge, close issue, dev build (delegated to /team-build per config.build), tracker sync. Prod is NEVER built here (see config.build.prodPolicy / config.nonNegotiables).'
argument-hint: '(no args — uses current branch)'
allowed-tools: [Read, Write, Bash, Glob, Grep, mcp__mempalace__mempalace_search, mcp__mempalace__mempalace_add_drawer, mcp__codegraph__codegraph_search]
model: opus
enabled: true
---

# /team-ship

## Resource Efficiency

- **Memory:** Vote record lookup: `mcp__mempalace__mempalace_search query="team-mode completion vote <issue>" wing="<config.memory.wing>"`. Stage-build log: `mcp__mempalace__mempalace_add_drawer wing="<config.memory.wing>" room="<config.memory.room>" name="stage-builds"`.
- **This skill runs on `opus`**. All approval gates wait at the terminal — do not escalate elsewhere.

## Label self-heal

If any `gh issue edit ... --add-label` or `gh pr create ... --label` fails with `'<label>' not found`, run `${CLAUDE_PLUGIN_ROOT}/scripts/setup_labels.sh` then retry the single operation. Do NOT run label-adjacent `gh` commands in parallel — if one fails, it cancels siblings.

## Preconditions
1. `<config.nonNegotiables>` loaded.
2. `/team-work` ended with a team DONE vote.
3. All tests green on current branch.
4. Working tree clean; branch pushed.
5. Team vote record available (MemPalace `mcp__mempalace__mempalace_search query="team-mode completion vote <issue>"` or this session).
6. Issue number known.

## Procedure

### 1. Version bump — MANDATORY (see `<config.nonNegotiables>`)

**Every merged PR must bump the version.** Not optional. A PR that closes an issue without a version bump is an incomplete ship.

Determine bump type from branch history: `git log develop..HEAD --format=%s`
- Any `feat` → minor
- Only `fix|chore|refactor|test|docs|perf|ci|build` → patch
- Any `BREAKING CHANGE` footer or `!` → major (confirm with user first)

**Source of truth:** `config.versionSource`. This project tracks the version there and nowhere else in-tree.

Apply the bump to `config.versionSource` using the project's version-bump command if it has one; otherwise edit the file directly:
```bash
# Example — bump the patch component of the version stored in config.versionSource
# (adjust to the file's format: a bare VERSION file, a package/build manifest, etc.)
```

**Do NOT skip the corresponding `CHANGELOG.md` entry.** Every version bump gets a new `## [X.Y.Z] - YYYY-MM-DD` section describing what changed. A version-bump tool does not always update CHANGELOG — verify and add the section manually if missing.

The git tag comes later (step 9) — that's the release's GitHub identity. `config.versionSource` alone is not sufficient.

Commit the bump:
```bash
git add -A  # version file + any files the bump touched (CHANGELOG, etc.)
git commit -m "chore(release): bump to vX.Y.Z"
```

**Do NOT push yet** (the hold-until-release-confirmation discipline in `<config.nonNegotiables>`). The bump commit stays local until the user says "confirm release" after the PR is ready for merge.

### 2. Open PR
```bash
gh pr create --base develop --title "<conventional-commit title> (#<N>)" --body "$(pr_body)" --label "<labels>"
```

**PR body template:**
```markdown
## Summary
<one paragraph>

## Closes
#<N>

## Changes
- <bullet>

## Test evidence
<paste test output, CI link>
Coverage delta: <+X lines covered>
Sample output: <representative config.impactVocabulary.protectedOutput snippet — scrubbed per the subscriber-data rule in config.nonNegotiables>

## Team vote record (completion)
<one line per voting member (config.members where votes == true), e.g.>
- product-owner: DONE — <brief>
- lead-developer: DONE — <brief>
- senior-developer: DONE — <brief>
- senior-dba: DONE | N/A — <brief>
- qa-security: DONE — <brief>
- lead-architect: DONE — <brief>

## Version bump
vX.Y.Z (mandatory — see config.nonNegotiables)

## Rollback plan
<how to revert if this breaks in dev>

## Non-negotiable checklist (per config.nonNegotiables)
- [ ] No prod DB writes
- [ ] No secrets in commits
- [ ] No real subscriber / PII identifiers
- [ ] No direct commits to main/develop
- [ ] No tests disabled
- [ ] Version bumped
- [ ] PO sign-off on changes to config.impactVocabulary.protectedOutput (if applicable)
```

Base **must** be `develop`. Never `main` (the no-direct-to-main rule in `<config.nonNegotiables>`).

### 3. Run `/team-review --pr <PR#>`
Team posts review block on the PR.

### 4. Fix loop
Any BLOCK or REQUEST_CHANGES → senior-developer addresses, push, re-run `/team-review --pr <N>` (only for agents who requested changes).

### 5. User approval gate — NON-NEGOTIABLE (user-approves-merge, `<config.nonNegotiables>`)
Once all APPROVE, print:
```
=== Ready to merge ===

PR:     <url>
Issue:  <url>
Branch: <branch>
Base:   develop
Version: X.Y.Z

Team review: all APPROVE.

I will not merge without your explicit approval. Options:
  "approve"      → I will merge and proceed with the build flow.
  "self-merge"   → you authorize me to merge THIS PR (single-use).
  "changes"      → leave open; describe what to change.
  "hold"         → leave open; you'll merge manually later.
  "confirm release" → same as "approve" + ok to push version bump.
```

Accept only explicit approval. Ambiguous response → ask again.

### 6. Record approval audit trail (MANDATORY before merge)

Once approval received, post a comment on the PR documenting it:
```bash
gh pr comment <PR-N> --body "**Reviewed and approved by @$(gh api user --jq .login) via /team-ship interactive approval gate.**

- Approval received at: $(date -u +%Y-%m-%dT%H:%M:%SZ)
- Approval mode: \`approve\` | \`self-merge\` | \`confirm release\` (fill actual)
- Team review: all APPROVE (see review comment above)
- Version bump: vX.Y.Z (version-bump rule satisfied)
- Non-negotiables checklist: complete"
```

This is the audit trail. It's permanent on the PR.

### 7. Push the version bump (hold-until-release-confirmation, `<config.nonNegotiables>`)
If approval was `"confirm release"` (or equivalent), push the version bump that's been sitting locally:
```bash
git push origin <branch>
```

If approval was `"approve"` or `"self-merge"` without explicit release confirmation, hold the push — remind the user they still need to confirm before any tag is pushed.

### 8. Merge + delete both remote AND local branch (MANDATORY)

```bash
# Merge with automatic remote-branch delete
gh pr merge <PR-N> --squash --delete-branch

# Delete local branch too — this is mandatory, not optional
git checkout develop
git pull --ff-only
git branch -D <branch>
```

The `git branch -D` step is required. A team-shipped PR leaves NO local branch behind.

### 9. Tag the release — MANDATORY (version authority on GitHub — see `<config.nonNegotiables>`)

**`config.versionSource` is not the only version source of truth. The git tag is.** Tracking a version only in `config.versionSource` makes the release invisible to GitHub's release UI, breaks `gh release list`, and means anyone inspecting the repo via tags cannot find the shipped version. Always tag.

After merge, on `develop` with the release commit checked out:
```bash
# Tag the merge commit. Annotated tag — the `-a` and `-m` are required.
git tag -a "vX.Y.Z" -m "Release vX.Y.Z — <PR-N>: <short summary>"
git push origin "vX.Y.Z"
```

Tag format is **`vX.Y.Z`** (leading `v`, matching the existing tag history — see `git tag -l` for prior examples).

Verify:
```bash
gh api "repos/$(gh repo view --json owner,name -q '.owner.login + \"/\" + .name')/tags?per_page=1" --jq '.[0].name'
# → must print vX.Y.Z
```

If the tag push fails (e.g., tag already exists on the remote), **stop** and investigate — do not force-push a tag. A duplicate tag means a prior ship attempt collided; that needs a human decision before proceeding.

### 10. Close the issue + sync tracker

```bash
gh issue close <issue-N> --reason completed \
  --comment "Merged in #<PR-N>. Version: vX.Y.Z (tagged). Build will follow."

# AUTO-SYNC the tracker spreadsheet — reflects the close immediately
if [ -f venv/bin/activate ]; then source venv/bin/activate; fi
python "${CLAUDE_PLUGIN_ROOT}/skills/team-sync-issues/sync_issues.py"
```

The sync keeps `tmp/_OPEN_ISSUES.xlsx` current — the just-closed issue moves to the "Recently Closed" sheet automatically.

### 11. Build for `dev` — ALWAYS runs after merge to develop
This step is mandatory. Do not skip. Even if the diff "doesn't look like it affects the build artifact" — rebuild. The build mechanics live in `/team-build` (driven by `config.build`); this step only triggers it.

```bash
# Invoke /team-build dev
```

### 12. Generate / refresh documentation (doc-discipline per `<config.nonNegotiables>`)

```bash
# Check if code changes require doc updates
/team-document --auto
```

The `--auto` flag inspects the merged diff and updates:
- CHANGELOG.md (always, on merge)
- docs/API_REFERENCE.md (if any blueprint/route changed)
- docs/CLI_REFERENCE.md (if any CLI command changed)
- Docstrings and inline comments (should be in the PR already per CLAUDE.md "DOCUMENT → CODE → TEST → COMMIT")

If doc updates are needed, they land on `develop` via a follow-up commit `docs: refresh reference docs for vX.Y.Z`.

### 13. Summary to user
```
✅ Shipped to dev.

  Merged:       <PR url>  (commit <sha>)
  Version:      vX.Y.Z (config.versionSource bumped + git tag pushed)
  Git tag:      vX.Y.Z  (git push origin vX.Y.Z — visible at gh release list)
  Approval:     Documented on PR per the user-approves-merge audit trail
  Build:        <per /team-build dev output — artifact ref per config.build>
  Issue:        #<N> closed + tracker spreadsheet synced
  Branches:     remote deleted, local deleted — clean state
  Docs:         refreshed (CHANGELOG + API/CLI reference if changed)

Next:
  - Stage promotion is manual. When ready: /team-build stage
  - Prod is gated and never shipped here (see config.deploy.prod / config.build.prodPolicy — /team-ship does NOT touch prod).
```

## What this command does NOT do
- **Does NOT build stage** unless user runs `/team-build stage` next.
- **Does NOT touch prod.** (see config.deploy.prod / config.build.prodPolicy / `<config.nonNegotiables>`)
- **Does NOT tag `main`.** Release decision, not a merge decision. (The `vX.Y.Z` tag in step 9 lives on `develop`; promoting to `main` is a separate, manual step.)
- **Does NOT skip the version bump, the git tag, the branch delete, or the approval audit comment** — those are all mandatory per `<config.nonNegotiables>`.
