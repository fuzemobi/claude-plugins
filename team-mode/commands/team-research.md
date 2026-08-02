---
name: team-research
description: 'Run the team research loop on a problem — each voting agent investigates independently, reports findings + structured vote, loop until 5-of-6 consensus with no domain-owner veto (max 3 rounds), then produce a Root Cause Brief ready for /team-plan.'
argument-hint: '<problem description OR --issue N OR --context>'
allowed-tools: [Read, Write, Bash, Glob, Grep, WebFetch, mcp__mempalace__mempalace_search, mcp__mempalace__mempalace_add_drawer, mcp__mempalace__mempalace_kg_add, mcp__codegraph__codegraph_search, mcp__codegraph__codegraph_context, mcp__codegraph__codegraph_callers, mcp__codegraph__codegraph_impact, mcp__fmx__generate]
model: opus
enabled: true
---

# /team-research

## Resource Efficiency

- **Memory:** `mcp__mempalace__mempalace_search query="<topic> <issue>" wing="<config.memory.wing>"` before reading files. Write findings with `mcp__mempalace__mempalace_add_drawer` + `mcp__mempalace__mempalace_kg_add`.
- **Code search:** `mcp__codegraph__codegraph_search` / `codegraph_context` / `codegraph_callers` / `codegraph_impact` — use these BEFORE grep or Read for any symbol lookup.
- **Codebase orientation (B3_warm):** before reading many files to understand an area, run `cgdigest <dir> --reduce` (or `python3 ~/.claude/skills/codebase-digest/cgdigest.py --dir <path> --reduce`). It returns cached skeleton+prose digests via Cerebras gpt-oss-120b — sub-second and nearly free on unchanged files. Use it to scope WHICH files matter, then drill in with `codegraph_context` / Read on those. Digests are orientation only; evidence still requires file:line.
- **Spawned voting agents:** use `model: sonnet` — they investigate, not orchestrate. Pass CodeGraph tool instructions to each agent.
- **Heavy analysis via fmx (Cerebras) — MANDATORY:** each voting agent routes bulk reading/summarization through `mcp__fmx__generate` — `mode="summarization"` for large files/logs, `mode="reasoning"` for hypothesis analysis. Defaults to gpt-oss-120b on Cerebras (off the Anthropic pool). Votes and cited evidence stay native; fall back to native after one retry on error.
- **This skill runs on `opus`** for synthesis and consensus judgment.

## Usage

```
/team-research "widget import rejects valid rows at step 4 with error 32"
/team-research --issue 326
/team-research --context          # use current conversation as context 
```

`--context` tells me to pull the problem from our current conversation rather than requiring a restatement.

## Procedure

### Setup
1. Read NON_NEGOTIABLES and team config.
2. Capture the problem in one paragraph; identify the domain(s) involved (this sets who has veto for this question).
3. Write an initial memory via the memory backend (`config.memory`): `mcp__mempalace__mempalace_add_drawer wing="<config.memory.wing>" room="<config.memory.room>" name="issue-<slug>-research-round-0"` — the problem statement and your initial read.

### Rounds (max 3)

For each round:
1. **Spawn each voting agent in parallel** — use the Task tool. Give each agent:
   - Problem statement
   - Relevant NON_NEGOTIABLES excerpt
   - Their persona file
   - Prior round findings (from round 2 onward)
   - Explicit instruction: investigate INDEPENDENTLY; do not confer with other agents this round
   - **Model: `sonnet`** — sufficient for investigation; reserve opus for orchestration
   - **Delegate heavy lifting to Cerebras:** use `mcp__fmx__generate` (`mode="summarization"` / `mode="reasoning"`, default gpt-oss-120b) for bulk file digestion and analysis — the vote and cited evidence stay native
   - **Code search: CodeGraph first** — use `mcp__codegraph__codegraph_search`, `codegraph_context`, `codegraph_callers`, `codegraph_impact` before grep or file reads
   - **Orientation: cgdigest first** — for "what does this module do" scoping, the agent may run `cgdigest <dir> --reduce` (Bash) to get a fast cached digest before reading files; cite file:line from CodeGraph/Read for any finding that tips consensus
2. **Collect returns** — each agent produces a report + a vote (see team-mode skill for format).
3. **Tally using the consensus rule** — 5-of-6 CONSENSUS + no domain-owner VETO.
4. **On no consensus**:
   - Summarize agreements, disagreements, gaps.
   - Write memory: `mcp__mempalace__mempalace_add_drawer wing="<config.memory.wing>" room="<config.memory.room>" name="issue-<slug>-research-round-<N>-synthesis"`.
   - Feed synthesis into next round; direct each agent to new evidence paths.
5. **On consensus**: produce the Root Cause Brief below.

### Evidence standards
A finding must include at least one of: file path + line, log line with timestamp, query result, schema excerpt, spec/contract reference, commit SHA. Opinion without evidence doesn't tip consensus.

### After round 3 with no consensus
Stop. Write escalation memory. Print:
```
Team investigated 3 rounds, no consensus.
Agree on: ...
Disagree on: <claim> — <agent> says X, <agent> says Y because ...
To proceed we need from you: <specific decision, access, or artifact>.
```

## Root Cause Brief output (on consensus)

> **Reference:** if a prior deep-dive investigation memo exists for this area, cite it here (e.g. `references/<prior-investigation>.md`).


```markdown
## Root Cause Brief — <issue/slug>

**Problem:** <one sentence>
**Root cause:** <one paragraph>
**Evidence:** <bullet list of artifacts>
**Confidence:** High | Medium | Low
**Vote record:**
- product-owner: CONSENSUS (High) — <reason>
- lead-architect: CONSENSUS (High) — <reason>
- lead-developer: CONSENSUS (High) — <reason>
- senior-developer: CONSENSUS (High) — <reason>
- senior-dba: CONSENSUS (Medium) — <reason>
- qa-security: CONSENSUS (High) — <reason>
**Proposed fix direction:** <one paragraph — direction, not design>
**Risks:** <bullets>
**Customer impact (`config.impactVocabulary.customerImpact`):** <from PO>

Next: `/team-plan` to draft the GH issue.
```

Write the brief to the memory backend (`config.memory`): `mcp__mempalace__mempalace_add_drawer wing="<config.memory.wing>" room="<config.memory.room>" name="issue-<slug>-research-brief"`.
