---
name: team-work
description: 'Create a Git worktree for the issue branch, then run the standard team‑work workflow.'
argument-hint: '<issue-number>'
allowed-tools: [Bash, Read, Write, Glob, Grep, mcp__mempalace__mempalace_search, mcp__mempalace__mempalace_add_drawer, mcp__codegraph__codegraph_search, mcp__codegraph__codegraph_context, mcp__codegraph__codegraph_callers, mcp__codegraph__codegraph_impact, mcp__codegraph__codegraph_node, mcp__fmx__generate]
model: opus
enabled: true
---

# /team-work

## Resource Efficiency

- **Code search:** Use CodeGraph BEFORE grep or Read — `mcp__codegraph__codegraph_search` to find symbols, `codegraph_context` for task-relevant code, `codegraph_callers`/`codegraph_callees` to trace impact, `codegraph_impact` before any change. Use `codegraph_node` for source + details on a specific function.
- **Codebase orientation (B3_warm):** before reading many files to understand an area, run `cgdigest <dir> --reduce` (or `python3 ~/.claude/skills/codebase-digest/cgdigest.py --dir <path> --reduce`). It returns cached skeleton+prose digests via Cerebras gpt-oss-120b — sub-second and nearly free on unchanged files. Use it to scope WHICH files matter, then drill in with `codegraph_context` / Read on those. Digests are orientation only; evidence still requires file:line.
- **Code generation (delegate to Cerebras via fmx):** for bulk new or modified code — test suites, refactors, boilerplate, scaffolding — call `mcp__fmx__generate` with `mode="code"`. It routes to gpt-oss-120b on Cerebras (off the Anthropic usage pool) and returns code as text; write it with native Write/Edit and review it. **Native fallback is mandatory** — if it errors, times out, or returns empty/malformed output, do not retry more than once: write the code yourself and continue. **Never delegate** test oracles/assertions, security-relevant checks, or correctness-critical logic — write those natively, every time.
- **Memory:** Check MemPalace for prior findings on this issue: `mcp__mempalace__mempalace_search query="issue-<N>" wing="<config.memory.wing>"`. Write phase completions with `mcp__mempalace__mempalace_add_drawer`.
- **This skill runs on `opus`**. Implementation subagents use `sonnet`; linter/test-runner subagents use `haiku`.

This skill extends the standard **team‑work** command by automatically creating a Git work‑tree for the feature branch associated with the given issue number before proceeding with the usual workflow.

## What it does
1. **Parse the issue number** passed as the argument (e.g. `705`).
2. **Derive the branch name** – we use `issue/<number>` (the same naming convention the original workflow expects). If the branch does not yet exist, we create it from `develop`.
3. **Create a work‑tree** in a sibling directory `../worktrees/issue-<number>`:
   ```bash
   cd <repo‑root>
   git fetch origin
   # If the branch does not exist, create it from develop
   if ! git rev-parse --verify "issue/<number>" >/dev/null 2>&1; then
       git checkout -b "issue/<number>" origin/develop
   fi
   # Make sure the work‑tree parent directory exists
   mkdir -p ../worktrees
   # Add the work‑tree (idempotent – if it already exists git will skip)
   git worktree add "../worktrees/issue-<number>" "issue/<number>"
   ```
4. **Change into the work‑tree** and invoke the original team‑work script (`team-work` binary or internal logic). For now we simply `cd` into the work‑tree and call the existing `./scripts/team-work.sh` placeholder (you can replace this with the real implementation). 
5. **Report back** the location of the work‑tree and the branch name.

## Usage
```
/team-work 705
```
The skill will output something like:
```
Created work‑tree at ../worktrees/issue-705 on branch issue/705
Running standard team‑work workflow…
```
You can then continue with the normal implementation steps (writing tests, code, PR, etc.) inside that isolated directory.

## Done gate — the machine check the loop closes on (NON-NEGOTIABLE)

A `/team-vote` completion round does **not** substitute for a passing build. Before any agent may vote `DONE`, the implementer must run the project's machine-readable gate and read the result — iterate until green, then vote.

The gate is the project machine gate — `config.machineGate.command` (labelled `config.machineGate.label`):
```bash
<config.machineGate.command>
```
- Loop on this: implement → run → read exit code → fix failures → re-run until it passes. The agent closes its own loop; it does not stop on "looks done."
- If the diff touches any path in `config.highRiskPaths`, or is a `config.highRiskChange` (migration/schema/etc.), the machine gate is **mandatory**. Changes to `config.impactVocabulary.protectedOutput` additionally require PO sign-off (a domain-owner veto lane — read `<config.nonNegotiables>`) — flag it, don't self-approve.
- **A `DONE` vote is invalid unless the green machine-gate exit line was produced in this session.** No pasted green output = the vote does not count toward consensus (see `team-mode/consensus.md` Step 0).

### Refutation pass (fresh-context check — the grader is not the worker)
After the machine gate is green, spawn ONE fresh subagent (the bundled `/code-review` skill, or `oh-my-claude:critic` / `qa-security` in a clean context) that sees only the diff and the plan/ACs — not the reasoning that produced it. Its task: *"prove this diff breaks `config.impactVocabulary.customerImpact` or `config.impactVocabulary.protectedOutput`, or misses a stated AC — find the case where it's wrong."* **Flag only gaps that affect correctness or the stated requirements; ignore style and hypothetical edge cases that can't occur** (a reviewer told to find gaps always finds some — chasing all of them causes over-engineering). A real correctness/AC failure reopens the completion loop. This is the playbook's adversarial review — the worker never grades its own work.

## Notes
- The skill only touches Git; it does **not** automatically push or create a PR. Those steps remain part of the regular team‑work flow.
- If a work‑tree already exists for the branch, `git worktree add` is safe and will simply re‑use the existing directory.
- Ensure the repository’s remote `origin` is configured and reachable – the skill runs `git fetch` to keep the branch list up to date.

---

*If you need to customise the work‑tree location or branch naming convention, edit the Bash script embedded in this skill.*