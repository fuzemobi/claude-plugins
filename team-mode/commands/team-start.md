---
name: team-start
description: 'Spin up the project team on an issue or problem. Entry point for the full research→plan→work→review→ship flow. Auto-routes based on where the issue is (new problem, Ready issue, in-flight).'
argument-hint: '<issue-number | problem-description>'
allowed-tools: [Read, Write, Bash, Glob, Grep, mcp__mempalace__mempalace_search, mcp__mempalace__mempalace_add_drawer, mcp__codegraph__codegraph_search, mcp__codegraph__codegraph_context]
model: opus
enabled: true
---

# /team-start

Entry point to team mode. Dispatches to the right sub-flow based on input.

## Usage

```
/team-start 326                      # known GH issue number
/team-start "widget import rejects    # free-text problem description
             valid rows at step 4"
/team-start --resume 326             # resume an in-flight issue from memory
```

## Resource Efficiency

- **Memory:** Search the memory backend (`config.memory`) before reading files — `mcp__mempalace__mempalace_search query="<topic>" wing="<config.memory.wing>"`. Write state with `mcp__mempalace__mempalace_add_drawer`.
- **Code search:** `mcp__codegraph__codegraph_search` / `codegraph_context` before grep or Read for symbol lookups.
- **This skill runs on `opus`** for orchestration reasoning. Delegate subagents at `sonnet`; status/script runners at `haiku`.

## Procedure

1. **Resolve + load team config**: read `<project>/.claude/team.json` → `{ "team": "<name>" }` → load `~/.claude/teams/<name>/config.json`. Everything below references `config.*`.
2. **Read `<config.nonNegotiables>`** — halt if missing.
3. **Check the memory backend** (`config.memory`) for existing state on this issue:
   ```
   mcp__mempalace__mempalace_search query="team-mode <issue#> status" wing="<config.memory.wing>"
   ```
   If a drawer exists for this issue, read it and summarize for the user before doing anything new.

4. **Branch based on input**:
   - **GH issue number** → `gh issue view <N>` to get state.
     - If state = Ready: go to `/team-work <N>`.
     - If state = In Progress + branch exists: resume at last phase from memory.
     - If state = Open/Triage: start with `/team-research <N>` using issue body as context.
     - If unclear: print options and ask user.
   - **Free-text problem** → start with `/team-research "<text>"`.
   - **`--resume <N>`** → read status memory, announce phase, ask user if they want to continue.

5. **Announce** in scrum-master style:
   ```
   📋 Team: <config.name> | Issue: <N> | Phase: <phase> | Members: <count of config.members>
   Next: <specific next command>
   ```

## Guardrails
- Never skip the non-negotiables read.
- Never start on `main` or `develop` uncommitted — check `git status` and stop if dirty.
- Never proceed past Ready without user confirmation if the issue's AC is unclear.
