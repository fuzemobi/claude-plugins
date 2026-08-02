---
name: team-mode
description: 'Use when the user invokes any /team-* command, says "spin up the team," references a project team, or when the project''s .claude/CLAUDE.md activates team mode. Enforces the research → plan → work → review → ship flow with a config-defined roster of voting technical agents plus a scrum-master orchestrator. Handles voting/consensus, context handoff before context limits, and non-negotiable guardrails. Stack- and domain-agnostic: all project specifics come from the team config.'
---

# Team Mode

Team mode is generic build + guardrail tooling. Nothing here is tied to a
language, deploy target, or business domain — every project-specific value is
read from the team config (see **Config resolution**). To onboard a new project
you drop one config + one pointer; you never edit these skill files.

## Activation

Team mode is live when ANY of these are true:
- The user types a `/team-*` command (`/team-start`, `/team-research`, `/team-vote`, `/team-status`, `/team-handoff`, `/team-ship`).
- Project-level `.claude/CLAUDE.md` declares `team-mode: on` or points to a team config.
- The user says "spin up the team" or "run this through the team."

When activated, **you (main Claude) are the scrum-master by default** — the
lightweight orchestrator. Read `<config.personasDir>/scrum-master.md` and behave
accordingly.

## Config resolution (do this first, every session)

1. **Resolve the team** for the current project: read `<project>/.claude/team.json`
   → `{ "team": "<name>" }` (or a `team: <name>` line in `<project>/.claude/CLAUDE.md`).
   If neither exists, ask the user which team config to use — do not assume one.
2. **Load** `~/.claude/teams/<name>/config.json`. Everything below references
   `config.*`; never hardcode a roster, gate command, path, or registry.
3. **Read `<config.nonNegotiables>`** (the project's `NON_NEGOTIABLES.md`). If
   absent, refuse to proceed and tell the user to create it.
4. **Check for an active team memory** via `config.memory` (see below). If there's
   an in-flight issue, summarize its state before doing anything new.

## The team

The roster, veto authority, and consensus thresholds are **defined in
`config.members` and `config.consensusRule`** — read them there, do not restate a
fixed roster here. Shape:

- One non-voting `scrum-master` (orchestrator).
- N voting technical agents, each with a `vetoAuthority` domain list.
- Consensus per `config.consensusRule` (typically 5-of-6 technical agreement + no
  valid domain-owner veto).

Personas live at `<config.personasDir>/<agentType>.md`.

## The flow

```
/team-start <issue#|problem-desc>
     ↓
/team-research   → independent investigation → /team-vote → CONSENSUS
     ↓
/team-plan       → draft GH issue w/ user story + AC + test evidence plan
     ↓
user approves issue
     ↓
/team-work <issue#> → branch → TDD loop → machine gate green → /team-vote DONE
     ↓
/team-ship → version bump → PR → /team-review → user approves merge → merge → /team-build (per config.build)
```

See: `consensus.md` for vote tally rules, `handoff.md` for context preservation.

## Choosing the lane: full council vs. lite

The full-council vote is the right tool for high-impact or structural change —
and overkill for a typo fix. Reach for the heavy flow when the single-agent loop
"feels boring," not by default.

**Lite lane** — run the implementer + the machine gate (`config.machineGate`) +
ONE refutation pass, then ship. **Skip the full vote.** Eligible only when ALL are true:
- The change is describable in one sentence.
- No migration and no `config.highRiskChange` (schema/index/etc.).
- Does not alter `config.impactVocabulary.protectedOutput` (if unsure whether it
  does, assume it does — use full council).
- Touches code only (docs, comments, logging, a localized bugfix with a reproducing test).

**Full council** (the flow above) is **mandatory** when ANY of these hold:
- A migration or a `config.highRiskChange`.
- A change to `config.impactVocabulary.protectedOutput` (a domain-owner veto lane).
- A change under any path in `config.highRiskPaths`.
- Cross-cutting structural change (module boundaries, deps — architect/lead domains).

The machine gate (Step 0 in `consensus.md`) and the refutation pass apply to
**both** lanes. The lite lane drops the *vote*, never the *verification*. When in
doubt, escalate to full council — under-voting a high-impact change is the
expensive mistake.

## Voting

Every voting agent returns exactly this JSON in a fenced block:

```json
{"agent":"<name>","phase":"research|completion|pr-review","vote":"<verdict>","confidence":"High|Medium|Low","reasoning":"<one sentence>","concerns":[],"blockers":[]}
```

Phase-specific verdicts:
- **research**: `CONSENSUS` / `DIG_DEEPER` / `VETO`
- **completion**: `DONE` / `MORE_WORK` / `VETO`
- **pr-review**: `APPROVE` / `REQUEST_CHANGES` / `BLOCK`

### Tally rules

1. A vote with `blockers` non-empty downgrades to `DIG_DEEPER` / `MORE_WORK` / `REQUEST_CHANGES` regardless of the stated vote.
2. `VETO` / `BLOCK` is honored only if the agent has veto authority over the domain in question (`config.members[].vetoAuthority`). Outside-domain veto → downgrades to `DIG_DEEPER` and gets noted.
3. **Consensus achieved when** `config.consensusRule` is satisfied AND no valid `VETO` / `BLOCK` from any domain owner on the domain in play.
4. Otherwise: loop. Max 3 rounds for research and completion. After round 3, escalate to user.
5. PR review: all-APPROVE required. Any BLOCK from a veto holder stops merge.

Tiebreakers:
- **Even split** (one abstains): no consensus, loop.
- **Domain conflict**: the owner of the domain more directly in play wins (`config.members[].vetoAuthority` decides the lane); ambiguous → escalate to user.
- **Lead vs Senior developer** on structure: Lead wins.
- **Business owner vs all others** on "done" for customer-impacting work (`config.impactVocabulary.customerImpact`): business owner wins.

### Anti-patterns (do NOT)
- Consensus theater — adjusting prompts so agents agree. Disagreement is data.
- Vote buying — showing one agent another's vote mid-round.
- Silent escalation — if handing to user, say so and say why.

## Context preservation

### Problem
Agent sessions have finite context. A deep investigation can exhaust it silently,
quality degrades. The scrum-master prevents this.

### Principles
1. **Main Claude (scrum-master) stays lightweight.** Don't read dozens of files yourself — spawn agents.
2. **Each subagent invocation is a fresh context.** Subagents read relevant memories, do focused work, write findings to memory, return.
3. **Memory is the blackboard.** The durable state lives in the memory backend
   named by `config.memory` (backend/wing/room), rooted at `config.memoryRoot`.
   `whats-next.md` (via `/handoff-create`) is the immediate session handoff.

### Handoff triggers
The scrum-master (or an agent itself) initiates a handoff when:

| Trigger                                             | Handoff type           |
|-----------------------------------------------------|------------------------|
| Agent has read > ~15 files in one investigation     | CONTINUATION (fresh)   |
| Agent signals "getting deep" / "context warming"    | CONTINUATION (fresh)   |
| Agent's phase is complete (e.g. research done)      | PHASE (to next phase)  |
| Question shifted domains                            | LATERAL (different agent) |
| Session is ending; user will resume later           | SESSION (to disk)      |

### Handoff procedure

1. **Write a memory** (backend per `config.memory`) at
   `<config.memoryRoot>/<issue#>/<phase>/<agent>-handoff`:
   ```md
   # Handoff: <agent> — <issue#> — <phase>
   ## Original task
   ## What I examined (files, logs, queries, commits)
   ## Findings so far
   ## Confidence: High | Medium | Low
   ## Next step (specific — file:line, query, question)
   ## Blockers encountered
   ## Votes cast so far
   ```
2. **Optionally also invoke `/handoff-create`** to write `whats-next.md` for the broader session.
3. **Update team status memory** at `<config.memoryRoot>/<issue#>/status`.
4. **Report to user** — terse: `🤝 Handoff: <agent> → <agent|fresh>. Reason: <reason>. Memory: <name>.`
5. **Spawn the next agent** with instructions: "Read memory `<name>`, continue from the Next Step."

### When context is already tight
If you detect high context use on THIS session:
1. Invoke `/handoff-create` immediately.
2. Write a team memory (per `config.memory`) summarizing where the team is.
3. Suggest the user start a fresh session with `/team-start --resume <issue#>`.

## Non-negotiables

Read `<config.nonNegotiables>` before the first action in every session and
re-check when about to do anything risky. Reference rules **by name/domain**, not
by number — each project's `NON_NEGOTIABLES.md` owns its own numbering.

On detection of a violation:
```
NON_NEGOTIABLE_ALERT
Rule: <name/domain> — <rule summary>
Conflicting request: <what was asked>
Why it conflicts: <one sentence>
Safe alternative: <what we can do instead>
Severity: 🔴 | 🟡
```

- 🔴 rules: **never** overridable by chat. User must update the file via PR to change the rule.
- 🟡 rules: overridable only with explicit per-instance user acknowledgment that NAMES the rule. Vague approvals don't count.
