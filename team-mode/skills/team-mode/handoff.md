# Context Handoff Protocol (sub-skill of team-mode)

How team mode preserves context when a subagent's window is filling or when phases shift. The main `SKILL.md` references this file.

## Principle

Main Claude (the scrum-master / PO facilitator) stays light. Technical work happens in spawned subagents, each with their own context window. When a subagent approaches its limit, it writes a memory and returns; a fresh instance reads the memory and continues.

## Memory tiers

| Tier | Location | Scope | Lifetime |
|------|----------|-------|----------|
| Session state | Team memory (backend per `config.memory`): `<config.memoryRoot>/<issue#>/<phase>/<agent>-*` | Per issue, per phase | Durable across sessions |
| Session bridge | `whats-next.md` in project root (via `/handoff-create`) | Per session | Until next session consumes it |
| Long-term project | Project long-term memory (`activeContext.md` or equivalent) | Per project | Always current |

Team mode writes:
- **Every round** → session-state team memory (per `config.memory`).
- **On phase transition OR context-depth trigger** → `whats-next.md` via existing `/handoff-create`.
- **At `/team-ship` success** → update the project long-term memory.

> Memory backend is whatever `config.memory.backend` names (the global default is
> MemPalace, wing `config.memory.wing`). A project may keep a secondary backend in
> parallel, but the durable team blackboard is the configured one.

## Handoff triggers (who decides)

### Self-initiated (agent decides)
The agent detects they're going deep:
- Read > ~15 files in one investigation
- Session context feels warm
- Hit a boundary that requires a different specialty

The agent writes the handoff memory and returns control to the scrum-master/PO with reason `context-depth` or `lateral`.

### Orchestrator-initiated (PO/scrum-master decides)
The facilitator observes:
- Phase is complete (research done → plan phase)
- Vote just concluded — need to engage different agents for next phase
- Session is ending (user signals wrap-up)

The facilitator calls `/team-handoff` with the appropriate reason.

### Why NOT the technical agents themselves deciding phase transitions
Agents have opinions about the work. They're biased toward "let me finish this one more thing." The PO/scrum-master sees the whole board — they're better positioned to call "stop, checkpoint, switch."

## Handoff types

| Type | Trigger | Action |
|------|---------|--------|
| **CONTINUATION** | Same agent role, context filling | Write memory, spawn fresh instance of same role, pass memory name |
| **PHASE** | Research complete → plan | Write memory, call next-phase command (`/team-plan`) |
| **LATERAL** | Question shifted domains | Write memory, engage different domain agent |
| **SESSION** | User ending the session | Write memory + `whats-next.md` + update `activeContext.md` |

## Handoff content (required fields)

```markdown
# Handoff — <agent> — Issue #<N> — Phase: <phase>
## Original task
## What I examined (files, logs, queries, commits)
## Findings so far
## Confidence: High | Medium | Low
## Next step (specific — file:line, exact query, specific question)
## Blockers encountered
## Votes cast so far
## Non-negotiables encountered
```

**"Next step" is the most important field.** It must be concrete enough that a fresh agent reads it and knows EXACTLY what to do first. "Continue the investigation" is a failed handoff. "Open `<file>` at line <N>, trace the <specific> branch, verify it fires for the <named> test fixture" is a successful handoff.

## Fresh-agent resume protocol

When a fresh agent is spawned post-handoff:

1. Read the handoff memory first (before anything else).
2. Read the canonical `<config.nonNegotiables>`.
3. Go directly to the "Next step" action — do NOT re-read files the previous agent already examined unless you need to verify something specific.
4. Write a new memory on return.

## When context is already too full on THIS session

If you (scrum-master) detect high context use in the current session:

1. Invoke `/handoff-create` immediately (writes `whats-next.md`).
2. Write a team memory (per `config.memory`) for the team.
3. Tell the user:
   > "Context is getting tight. I've written a handoff. Start a fresh session and say `/team-start --resume <issue#>`. Nothing lost."

Don't wait until the session is incoherent — checkpoint early.

## Anti-patterns
- **Handoff-then-keep-going** — once you've written the handoff, return. Don't try to "just finish this one thing."
- **Vague "next step"** — if you can't name a file:line, you haven't done the handoff properly.
- **No memory, just `whats-next.md`** — both are needed. Team memory (per `config.memory`) survives across sessions and is team-scoped; `whats-next.md` is session-scoped and cwd-scoped.
- **Memory with sensitive/PII data** — see the PII/subscriber-data rule in `<config.nonNegotiables>`. Scrub before writing.
