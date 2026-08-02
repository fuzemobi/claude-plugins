---
name: team-status
description: '"Where are we?" — the scrum-master (PO) reports the current state of team work. Reads memory, summarizes phase, blockers, next action.'
argument-hint: '[<issue-number>] (optional — specific issue; default is active issue)'
allowed-tools: [Read, Bash, mcp__mempalace__mempalace_search, mcp__mempalace__mempalace_get_drawer]
model: sonnet
enabled: true
---

# /team-status

## Resource Efficiency

- **Memory:** `mcp__mempalace__mempalace_search query="team-mode <issue#>" wing="<config.memory.wing>"` — semantic search is faster than listing all memories.
- **This skill runs on `sonnet`** — status reporting does not require deep reasoning.

## Usage
```
/team-status          # active team work
/team-status 326      # specific issue
```

## Procedure

1. **Load state**:
   - `mcp__mempalace__mempalace_search query="team-mode <issue#> status phase" wing="<config.memory.wing>"` — read the most recent matching drawer
   - `gh issue view <N> --json state,labels,assignees,title`
   - `git status --porcelain`, `git branch --show-current`

2. **Report** (terse, scrum-master style):
```
📋 Team Status — Issue #<N>: <title>
State: <Ready|In Progress|In Review|Done>
Phase: research | plan | work | review | ship
Branch: <branch or — >
Working tree: clean | <N> files modified
Last vote: <phase> — <result> at <timestamp>
Blockers: <count> — <list or "none">

Team stance:
  product-owner:    <last vote or "not voted">
  lead-architect:   <...>
  lead-developer:   <...>
  senior-developer: <...>
  senior-dba:       <...>
  qa-security:      <...>

Next: <specific next command>
```

3. **If no in-flight work**:
```
📋 No active team work.
Recent issues: <list last 3 from memory>
Start with: /team-start <issue#> or /team-research "<problem>"
```

## Use cases
- Beginning of a session: "where did we leave off?"
- Mid-session: "who's blocking who?"
- After a long break: before running any action, confirm state matches your mental model.
