---
name: team-review
description: 'Run a full team code review on the current branch — each reviewer inspects the diff through their lens, returns a structured review block. Used pre-PR (internal) and during /team-ship (on the PR).'
argument-hint: '[--pr <pr-number>] (optional — posts review to PR if given)'
allowed-tools: [Read, Bash, Glob, Grep, mcp__mempalace__mempalace_search, mcp__mempalace__mempalace_add_drawer, mcp__codegraph__codegraph_search, mcp__codegraph__codegraph_context, mcp__codegraph__codegraph_impact, mcp__codegraph__codegraph_callers, mcp__fmx__generate]
model: opus
enabled: true
---

# /team-review

## Resource Efficiency

- **Code search:** For each changed file, run `mcp__codegraph__codegraph_impact` to surface call-chain effects before concluding a review. Use `codegraph_callers` to check whether changed functions are used in unexpected places.
- **Codebase orientation (B3_warm):** before reading many files to understand an area, run `cgdigest <dir> --reduce` (or `python3 ~/.claude/skills/codebase-digest/cgdigest.py --dir <path> --reduce`). It returns cached skeleton+prose digests via Cerebras gpt-oss-120b — sub-second and nearly free on unchanged files. Use it to scope WHICH files matter, then drill in with `codegraph_context` / Read on those. Digests are orientation only; evidence still requires file:line.
- **Memory:** `mcp__mempalace__mempalace_search query="issue-<N> completion vote" wing="<config.memory.wing>"` to load prior vote context.
- **Reviewer subagents:** spawn at `model: sonnet`. Each gets the diff + their lens + a `codegraph_impact` instruction.
- **Heavy analysis via fmx (Cerebras) — MANDATORY for reviewers:** each reviewer routes bulk diff comprehension through `mcp__fmx__generate` — `mode="summarization"` to digest large diffs/files, `mode="reasoning"` for impact analysis. Defaults to gpt-oss-120b on Cerebras (off the Anthropic pool). The reviewer's own VERDICT, severity calls, and security judgments are made natively — never delegated. Fallback: if fmx errors or returns empty, retry once, then proceed natively.
- **This orchestrator runs on `opus`** to synthesize all reviewer blocks.

## Preconditions
1. `<config.nonNegotiables>` loaded.
2. Current branch is not `main` or `develop`.
3. There is a diff against `develop`.

## Procedure

### 1. Gather the diff
```bash
git fetch origin develop
git diff origin/develop...HEAD --stat
git diff origin/develop...HEAD
```

If diff > ~2000 lines: warn the user. Too big for one PR — probably should be split.

### 2. Dispatch to reviewers (parallel)

Spawn each as a subagent at **`model: sonnet`**. Pass the diff output and instruct each to: (a) run `mcp__codegraph__codegraph_impact` on changed symbols before filing findings, and (b) use `mcp__fmx__generate` (Cerebras gpt-oss-120b) for bulk diff summarization and reasoning per the Resource Efficiency rules — verdicts stay native.

- **lead-developer** — code structure, library choices, typing, logging, error handling, test quality.
- **senior-dba** — any DB or data-pipeline change. Returns `N/A` if none.
- **lead-architect** — cross-cutting concerns, interface changes, coupling, operational envelope.
- **qa-security** — coverage per changed line, security checklist, secret scan, dep scan.
- **product-owner** — does this satisfy the AC? Is partner behavior unchanged unless AC says so?

Note: **senior-developer does NOT review their own code** — they respond to comments.

### 3. Review block format (each reviewer)
```yaml
reviewer: <agent>
verdict: APPROVE | REQUEST_CHANGES | BLOCK
summary: <one sentence>
comments:
  - path: <file>
    line: <N>
    severity: info | suggestion | major | blocker
    comment: <text>
blockers: []   # non-empty only when verdict is BLOCK
```

### 4. Aggregate
- Any `BLOCK` from a veto holder **in their domain** → stops merge. Summarize blocker to user.
- All `APPROVE` → ready for user approval (the user-approves-merge rule in `<config.nonNegotiables>`).
- Mixed APPROVE/REQUEST_CHANGES with no BLOCK → senior-developer addresses, re-run `/team-review` on only the agents who requested changes.

### 5. Post to PR (if `--pr <N>` given)
```bash
gh pr review <N> --comment --body "<aggregated review>"
```
**Never** use `--approve` on the user's behalf — user approval is a human act (the user-approves-merge rule in `<config.nonNegotiables>`).

## Non-negotiable reminders for reviewers
Reference `<config.nonNegotiables>` by name/domain; each project owns its own rule numbering.
- **Secrets-in-git** — a secret in the diff → BLOCK immediately, tell user to rotate.
- **Subscriber / PII data** — a real protected identifier in the diff → BLOCK.
- **No disabling tests** — tests disabled/deleted → BLOCK unless each has a documented acceptable reason.
- **No unlinked TODOs** — a bare TODO → REQUEST_CHANGES, ask for linked issue.
- **Protected output** — a change to `config.impactVocabulary.protectedOutput` without PO sign-off → BLOCK (PO's vote is mandatory here).
