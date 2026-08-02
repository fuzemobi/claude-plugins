---
name: team-handoff
description: 'Explicit context handoff — write a MemPalace memory + whats-next.md capturing current team state, so a fresh agent (or a fresh session) can resume with zero loss. Invoked proactively when context depth is rising or at phase transitions.'
argument-hint: '[--reason <context-depth|phase-complete|session-end|lateral>] [--to <agent-name>]'
allowed-tools: [Read, Write, Bash, mcp__mempalace__mempalace_search, mcp__mempalace__mempalace_add_drawer, mcp__mempalace__mempalace_update_drawer, mcp__mempalace__mempalace_kg_add, mcp__codegraph__codegraph_context]
model: opus
enabled: true
---

# /team-handoff

## Resource Efficiency

- **Memory:** Use `mcp__mempalace__mempalace_add_drawer` + `mcp__mempalace__mempalace_kg_add` for handoff state. Use `mcp__mempalace__mempalace_update_drawer` to update existing status. Wing: `<config.memory.wing>`, room: `<config.memory.room>`.
- **Code context:** Run `mcp__codegraph__codegraph_context` on the primary changed files before writing the handoff — gives the receiving agent instant orientation without re-reading.
- **Codebase orientation (B3_warm):** for a multi-file summary, run `cgdigest <dir> --reduce` (or `python3 ~/.claude/skills/codebase-digest/cgdigest.py --dir <path> --reduce`) to fold the touched area into a cached skeleton+prose digest via Cerebras gpt-oss-120b — sub-second on unchanged files. Use it to write the handoff's "what changed / what matters" summary faster; cite file:line for anything load-bearing.
- **This skill runs on `opus`** for synthesis. Receiving agent spawned at `sonnet`.

## When to use
- Current agent has read ~15+ files in one investigation (context warming).
- Phase complete (e.g., research → plan).
- Question shifted domains (one domain → another).
- Session is ending; want to resume tomorrow.

## Usage
```
/team-handoff --reason context-depth --to senior-developer-fresh
/team-handoff --reason phase-complete
/team-handoff --reason session-end
```

## Procedure

### 1. Write MemPalace memory
Use: `mcp__mempalace__mempalace_add_drawer wing="<config.memory.wing>" room="<config.memory.room>" name="issue-<N>-<phase>-<agent>-handoff"`

Content:
```markdown
# Handoff — <agent> — Issue #<N> — Phase: <phase>

## Original task
<what this agent was doing>

## What I examined
- Files: <list>
- Logs: <list>
- Queries: <list>
- Commits reviewed: <list>

## Findings so far
<bullet findings>

## Confidence: High | Medium | Low

## Next step (specific)
<exactly what the next agent should do — file:line, query, question>

## Blockers encountered
<list>

## Votes cast so far (this issue)
<list>

## Relevant NON_NEGOTIABLES encountered
<any triggered — e.g., "considered a migration against a shared/prod DB, refused per the shared-DB migration rule in config.nonNegotiables">
```

### 2. Call existing `/handoff-create` for session-level continuity
This writes `whats-next.md` in the current working directory, using the existing session handoff format.

### 3. Update team status memory
Search with `mcp__mempalace__mempalace_search query="issue-<N> status" wing="<config.memory.wing>"`, then `mcp__mempalace__mempalace_update_drawer` — update current phase, active agent, next action.

### 4. Report to user (terse)
```
🤝 Handoff written
  Reason: <reason>
  Memory: MemPalace <config.memory.wing>/<config.memory.room>/issue-<N>-<phase>-<agent>-handoff
  Session file: <cwd>/whats-next.md
  Next: <agent|fresh|new-session>
  Resume with: /team-start --resume <issue#>
```

### 5. If `--to <agent>` given
Spawn that agent with instructions:
> "Search MemPalace: `mcp__mempalace__mempalace_search query='issue-<N>-<phase>-<agent>-handoff' wing='<config.memory.wing>'`. Continue from the 'Next step' section. Do not re-read files already examined unless verifying something specific. Use CodeGraph (`mcp__codegraph__codegraph_search`, `codegraph_context`) for any new code lookups."

## Non-negotiables
Referenced by name/domain — read `<config.nonNegotiables>` for the project's exact rules and numbering.
- **Subscriber / PII data**: handoff memory must not contain real subscriber/PII identifiers. Scrub before writing.
- **Secrets-in-git**: no secrets in memory files. They're on disk and durable — treat like git.
- **Data locality**: memory is local to the workstation; ensure it's not synced to any third-party service.
