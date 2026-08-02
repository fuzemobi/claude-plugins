---
name: team-plan
description: 'Turn a Root Cause Brief from /team-research into a draft GitHub issue — user story, acceptance criteria, test-evidence plan, customer impact. Asks for user approval before creating the issue.'
argument-hint: '(no args — uses last research brief in memory)'
allowed-tools: [Read, Write, Bash, Glob, Grep, mcp__mempalace__mempalace_search, mcp__mempalace__mempalace_add_drawer, mcp__codegraph__codegraph_search, mcp__codegraph__codegraph_context]
model: opus
enabled: true
---

# /team-plan

Takes the Root Cause Brief written by `/team-research` and drafts a GitHub issue the PO would sign off on.

## Resource Efficiency

- **Memory:** `mcp__mempalace__mempalace_search query="research-brief <slug>" wing="<config.memory.wing>"` to find the prior brief. Write the draft issue plan with `mcp__mempalace__mempalace_add_drawer`.
- **Code search:** `mcp__codegraph__codegraph_search` / `codegraph_context` before grep for any symbol lookup.
- **Codebase orientation (B3_warm):** before reading many files to understand an area, run `cgdigest <dir> --reduce` (or `python3 ~/.claude/skills/codebase-digest/cgdigest.py --dir <path> --reduce`). It returns cached skeleton+prose digests via Cerebras gpt-oss-120b — sub-second and nearly free on unchanged files. Use it to scope WHICH files matter, then drill in with `codegraph_context` / Read on those. Digests are orientation only; evidence still requires file:line.
- **This skill runs on `opus`**. Issue creation pauses for user approval — just wait at the terminal gate; do not escalate elsewhere.

## Preconditions
1. `<config.nonNegotiables>` loaded.
2. A Root Cause Brief exists — either from a prior `/team-research` in this session, or in the memory backend (`config.memory`): `mcp__mempalace__mempalace_search query="research-brief <issue-or-slug>" wing="<config.memory.wing>"`.
3. If no brief exists, decline and suggest `/team-research` first.

## Procedure

1. **PO drafts** (primary lead per their persona):
   - Title (imperative, scoped, ≤80 chars)
   - User story (As a … I want … So that …)
   - Acceptance criteria (Given/When/Then — minimum 3, include a negative case)
   - Customer impact (`config.impactVocabulary.customerImpact` — who/what is affected, risk level, timing constraints)

2. **Lead-architect drafts**:
   - Scope boundary (what this issue does NOT do — non-goals)
   - ADR references or a new-ADR-needed flag

3. **QA/Security drafts**:
   - Test-evidence plan (artifacts that will prove "done")
   - Specific tests to write (names and type: unit / integration / acceptance / regression / property)
   - Security review checklist items

4. **Senior-DBA drafts** (only if DB/data involved):
   - Schema changes (with reverse migration)
   - Query/plan impact
   - Migration plan + rollback

5. **Assemble** into the issue template below and show the user.

6. Ask: "Ready to create this issue in GitHub? (yes / edit / cancel)"

7. On yes:
   ```bash
   # Label self-heal: if any of the labels don't exist, create them first
   "${CLAUDE_PLUGIN_ROOT}/scripts/setup_labels.sh" 2>/dev/null || true
   gh issue create --title "..." --body "..." --label "ready,team-mode,..."
   ```
   Print the issue URL.

## Issue template

```markdown
## Summary
<one paragraph>

## Root cause
<from brief>

## User story
As a <role>
I want <capability>
So that <business outcome>

## Acceptance criteria
- [ ] Given … When … Then …
- [ ] Given … When … Then …
- [ ] Given … When … Then … (negative case)

## Test evidence plan
- [ ] <artifact 1 — e.g., "`config.machineGate.label` gate green against the affected fixture">
- [ ] <artifact 2 — e.g., "regression test `test_issue_<N>_<case>` passes">
- [ ] <artifact 3>

## Out of scope
- <what this issue is NOT doing>

## Schema / data impact
<if applicable>

## Customer impact (`config.impactVocabulary.customerImpact`)
- Affected scope: <list>
- Risk: <low/med/high + reasoning>
- Timing constraint: <when this must land>

## Risks
- <risk>

## References
- <linked issues, ADRs, docs>
- Research brief: memory backend `<config.memoryRoot>/issue-<slug>-research-brief`

## Team vote record (research phase)
<each agent, final vote from /team-research>
```

## Label suggestions (pick from what the repo uses)
`bug` | `feature` | `chore` | `refactor` | `area:<domain>` | `subsystem:<module>` | `priority:P0-P2` | `needs-po-signoff`

## After the issue is created

1. Print the issue URL.
2. Apply the `ready` label:
   ```bash
   gh issue edit <N> --add-label "ready,team-mode"
   ```
3. **Auto-sync the tracker spreadsheet** (MANDATORY — the new issue must appear in `tmp/_OPEN_ISSUES.xlsx`):
   ```bash
   if [ -f venv/bin/activate ]; then source venv/bin/activate; fi
   python "${CLAUDE_PLUGIN_ROOT}/skills/team-sync-issues/sync_issues.py"
   ```
   The script auto-backs up, adds the new row with auto-inferred Priority + Type from labels + title prefix. Priority and Type are inferred ONLY for new rows — never overwritten on existing ones.

4. Remind the user: `/team-work <issue#>` to start implementation.

## Non-negotiables
Read `<config.nonNegotiables>` and reference rules by name/domain, not number:
- **Permission discipline**: you do not create or approve anything on the user's behalf beyond drafting. Creation of the issue happens only after explicit user approval.
- **Scope discipline**: the issue's scope is the scope — do not pad it with adjacent work.
