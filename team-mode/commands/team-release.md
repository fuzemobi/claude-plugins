---
name: team-release
description: 'Roll a SHIPPED, version-tagged release into an environment — run open migrations, then build/deploy per the team config''s `deploy` block. Prod policy and deploy mechanics come from config; prod commonly requires sign-off and never builds. Stack- and cloud-agnostic.'
argument-hint: '<dev | stage | prod> [--version vX.Y.Z] [--skip-migrations] [--dry-run]'
allowed-tools: [Read, Bash, Glob, Grep, mcp__mempalace__mempalace_search, mcp__mempalace__mempalace_add_drawer]
model: opus
enabled: true
---

# /team-release

Promotes a **shipped release** (already merged and tagged `vX.Y.Z` by `/team-ship`)
into a running environment. All project/cloud specifics come from the resolved
team config's `deploy` block — this command hardcodes no cloud account, cluster,
service, migration path, or DB host.

## Config resolution (first)
Resolve the team: `<project>/.claude/team.json` → `{team:<name>}` → load
`~/.claude/teams/<name>/config.json`. Use `config.deploy`, `config.build.prodPolicy`,
`config.versionSource`, `config.machineGate`, `config.memory`, `<config.nonNegotiables>`.

## Step 0 — resolve version + env
```bash
ENV="$1"   # dev | stage | prod
echo "$ENV" | grep -qE '^(dev|stage|prod)$' || { echo "usage: /team-release <dev|stage|prod> [--version vX.Y.Z]"; exit 1; }
# VERSION from config.versionSource (VERSION | pyproject.toml | package.json | composer.json)
echo "release v$VERSION → $ENV"
```
Confirm a shipped release exists: the `vX.Y.Z` tag is present and matches
`config.versionSource`. If `--version` is omitted, use the tag at the default
branch HEAD.

## Step 1 — open migrations (if the project has any)
If the team config / project defines migrations, detect open ones (a numbered
migration with no applied-record for the target env) and apply them in order.
General rules (defer to `<config.nonNegotiables>` for the authoritative ones):
- Every migration must have a paired rollback — verify before applying; missing → STOP.
- Back up before any destructive or large-row migration (no "just dev" exception).
- Confirm the target env DB host before applying anything.
- `--skip-migrations` only when you've confirmed none are open.
If the project defines no migrations, skip this step.

## Step 2 — deploy per config.deploy

Determine the deploy path from `config.deploy`:

1. **`config.deploy.script` present** (e.g. `deploy.sh`): run it for the env, after
   the prod gate below.
   ```bash
   <config.deploy.script> "$ENV"      # e.g. deploy.sh dev
   ```
2. **`config.deploy.runbook` present**: follow that team-local runbook verbatim
   (it holds the cloud-specific register-task-def / roll-service / image steps).
3. **Neither**: STOP — the team config has no deploy path; tell the user.

### prod gate (always, before any prod deploy)
- If `config.build.prodPolicy == "refuse"`, a prod **build** here is refused; a
  prod **deploy** of an already-built, version-pinned artifact is allowed only if
  the artifact already exists — if it doesn't, STOP and route to a build/CI first.
- Sign-off on record for the release (per config roster / non-negotiables).
- Explicit terminal confirmation: print the gate and WAIT.
  ```
  === Prod deploy gate — v${VERSION} ===
  Artifact:  <exists? built by CI/dev>
  Target:    <env target from runbook/script>
  Migrations applied: <list or none>
  Rollback:  <previous revision — captured before the roll>
  Reply "deploy prod v${VERSION}? yes" to proceed, or "hold".
  ```
- Capture and print the rollback target BEFORE rolling.

## Step 3 — test (always)
- Machine gate: `config.machineGate.command` — must pass.
- Any deeper env/DB validation the project defines — must pass before a prod deploy is declared good; warn (don't silently accept) if it skips.
- Service/health check appropriate to the deploy target: confirm the new revision is stable and healthy.

## Step 4 — report + log
```
✅ team-release <env> — v${VERSION}
  Migrations:  <applied list | none>
  Artifact:    <id/digest>
  Deploy:      <what rolled>  (rollback: <prev>)
  Tests:       gate <pass>; env-validation <pass|skipped>
  Health:      stable
```
Append: `mcp__mempalace__mempalace_add_drawer wing=<config.memory.wing> room=<config.memory.room> name="releases"` — timestamp, version, env, artifact id, who approved, migrations applied.

## REFUSES / hard gates (by name — see config.nonNegotiables)
- **prod build** when `config.build.prodPolicy == "refuse"` → REFUSED; prod is deploy-only of an existing artifact.
- **prod deploy without sign-off or explicit "deploy prod vX.Y.Z? yes"** → STOP.
- **migration without paired rollback, or destructive/large-row migration without a backup** → STOP.
- **secrets or sensitive fixtures baked into the artifact** → STOP.
