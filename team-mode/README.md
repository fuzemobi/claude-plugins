# team-mode

A **config-driven multi-agent engineering team** for Claude Code. One plugin gives you a complete research → plan → work → review → ship workflow run by a roster of voting specialist agents — with structured consensus, domain-owner vetoes, machine-verified done gates, context handoffs, and a GitHub-native paper trail.

## The idea

A single agent grading its own work is the failure mode this plugin exists to prevent. team-mode splits engineering work across a roster of role-agents (product owner, architect, lead dev, implementer, DBA, QA/security) who:

- **investigate independently** and must produce *evidence* (file:line, log line, query result, commit SHA) — opinion doesn't tip consensus;
- **vote in a structured format** with explicit verdicts, confidence, and blockers;
- **hold vetoes only in their own domain** — the DBA can block a schema change, not a CSS tweak;
- **never self-grade** — the worker that produced a diff is not the one that reviews it, and a `DONE` vote is *invalid* unless the project's machine gate (your test/lint command) went green in the same session;
- **hand off context deliberately** — when an agent's window fills, it writes a structured handoff memory and a fresh instance resumes from an exact "next step," not from scratch.

Everything project-specific — roster, veto domains, test command, version file, build registry, deploy script, memory backend — lives in **one config file**. The plugin's commands and skills never hardcode a stack. Onboarding a new project is one config + one pointer file.

## Install

```
/plugin marketplace add fuzemobi/claude-plugins
/plugin install team-mode@fuzemobi-plugins
```

## Setup (per project, ~10 minutes)

1. **Create a team config** — copy [`examples/config.example.json`](examples/config.example.json) to `~/.claude/teams/<team-name>/config.json` and fill in your roster, machine-gate command, version source, and (optionally) build/deploy blocks.
2. **Point the project at it** — `<project>/.claude/team.json`:
   ```json
   { "team": "<team-name>" }
   ```
3. **Write `NON_NEGOTIABLES.md`** in the project root — the rules the team may never break (no prod writes, no secrets in git, user approves merges, …). Commands refuse to run without it, by design.
4. **Create the workflow labels** — `/team-setup-labels` (idempotent, one-time per repo).
5. Optional: write persona files for your roster at `<personasDir>/<agentType>.md`; define agents of the same names in `.claude/agents/` if you want distinct system prompts per role.

## The flow

```
/team-start <issue#|problem>
     ↓
/team-research   → each agent investigates independently → /team-vote → CONSENSUS
     ↓             (max 3 rounds; evidence required; Root Cause Brief output)
/team-plan       → draft GitHub issue: user story, AC, test-evidence plan
     ↓             (user approves before creation)
/team-work <N>   → worktree branch → TDD loop → machine gate green → refutation pass → DONE vote
     ↓
/team-ship       → version bump → PR → /team-review (5 reviewer lenses) → USER approves merge
     ↓             → merge → tag → close issue → /team-build dev → /team-document
/team-release    → migrations + deploy per config (prod gated; prod builds commonly refused)
```

Small change? A **lite lane** (implementer + machine gate + one refutation pass, no full vote) is defined for one-sentence, low-risk changes — the vote is skipped, the *verification* never is.

## Commands

| Command | What it does |
|---|---|
| `/team-start` | Entry point; routes by issue state (new → research, ready → work, in-flight → resume) |
| `/team-research` | Parallel independent investigation, evidence standards, consensus loop, Root Cause Brief |
| `/team-plan` | Brief → draft GH issue (story, AC incl. negative case, test-evidence plan); user approves |
| `/team-work` | Git worktree per issue, TDD loop, machine done-gate, fresh-context refutation pass |
| `/team-vote` | Structured vote: verdicts, blocker normalization, veto validation, tally, audit memory |
| `/team-review` | Five reviewer lenses in parallel (structure, DB, architecture, QA/sec, product); BLOCK stops merge |
| `/team-ship` | Version bump + CHANGELOG, PR with vote record, approval audit comment, merge, tag, branch cleanup |
| `/team-build` | Env-aware artifact build from `config.build`; prod policy commonly `refuse` (CI-only) |
| `/team-release` | Migrations (rollback-paired, backed up) + deploy per `config.deploy`; hard prod gate |
| `/team-document` | Docstring-drift detection, CHANGELOG, regenerated reference docs |
| `/team-status` | "Where are we?" — phase, branch, blockers, per-agent stance, next command |
| `/team-handoff` | Structured context handoff (memory + `whats-next.md`) with a concrete next step |
| `/team-setup-labels` | Idempotent GitHub label bootstrap (ready / in-progress / in-review / …) |
| `/team-sync-issues` | Two-way GH ↔ xlsx tracker sync (GH owns status; humans own priority/notes) |
| `/team-sync-document` | Regenerates PROJECT_REFERENCE.md (API routes + CLI commands) between `<!-- generated -->` markers |

## Skills

- **`team-mode`** — the core rules: activation, config resolution, full-council vs lite lane, vote tally, tiebreakers, anti-patterns (consensus theater, vote buying), non-negotiable alerts. Sub-docs: [`consensus.md`](skills/team-mode/consensus.md) (strict tally order — the machine gate precedes any completion vote) and [`handoff.md`](skills/team-mode/handoff.md) (memory tiers, handoff types, fresh-agent resume protocol).
- **`team-sync-issues`** — the GH↔spreadsheet sync contract: which side owns which column, inference tables for type/priority/status, automatic backups.

## What makes it different

- **Verification outranks opinion.** The consensus protocol's Step 0: a completion vote without the machine gate's green exit line *in the transcript* counts as `MORE_WORK`, whatever the agent said.
- **Vetoes are scoped.** An agent vetoing outside their domain gets downgraded and noted — authority comes from the config, not from confidence.
- **The user stays sovereign.** Issue creation, merges, releases, and prod anything require explicit human approval; the merge approval is recorded as a permanent PR comment.
- **Anti-patterns are named.** Consensus theater (tuning prompts until agents agree), vote buying (leaking one agent's vote to another mid-round), and silent escalation are explicitly forbidden.
- **Context is managed, not hoped about.** Handoffs are structured documents whose most important field is a concrete next step ("open file X at line N, trace branch Y") — "continue the investigation" is defined as a failed handoff.

## Optional integrations (degrade gracefully)

The commands reference some accelerator tools from the author's environment: a memory MCP backend (`config.memory` — MemPalace by default, but any backend or plain files work), a code-graph MCP for symbol search, and an off-model bulk-generation route. **None are required.** Without them, agents fall back to grep/Read and native generation; the workflow, gates, and votes are unchanged. Set `config.memory.backend` to `"file"` to keep team state in plain files.

## Prerequisites

- `gh` CLI authenticated (issues, labels, PRs, releases)
- `git` with worktree support
- Python 3.9+ with `openpyxl` (only for the xlsx tracker sync)
- A test/lint command for your project worth gating on (`config.machineGate.command`)

## License

MIT
