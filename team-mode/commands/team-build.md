---
name: team-build
description: 'Build and push the project''s release artifact for a target environment (dev | stage | prod), driven entirely by the team config''s `build` block. Dev is typically automatic after /team-ship merge. Prod policy is set by config.build.prodPolicy (commonly "refuse" — prod is CI-only). Stack-agnostic.'
argument-hint: '<dev | stage | prod> [--from <branch-or-tag>] [--skip-tests]'
allowed-tools: [Read, Bash, Glob, Grep, mcp__mempalace__mempalace_add_drawer]
model: haiku
enabled: true
---

# /team-build

Generic build/push wrapper. All project specifics come from the resolved team
config's `build` block — this command hardcodes no registry, Dockerfile, cloud
account, or test command. Also invoked automatically by `/team-ship` for `dev`.

## Config resolution (first)
Resolve the team: `<project>/.claude/team.json` → `{team:<name>}` → load
`~/.claude/teams/<name>/config.json`. Use `config.build`, `config.versionSource`,
`config.machineGate`, `config.memory`, and `<config.nonNegotiables>`.

## Resource efficiency
- **Runs on `haiku`** — it executes bash build commands; no heavy reasoning.
- Gated builds wait for user confirmation at the terminal — just wait; do not escalate elsewhere.
- Log successful non-dev builds to memory: `mcp__mempalace__mempalace_add_drawer wing=<config.memory.wing> room=<config.memory.room> name="builds"`.

## Usage
```
/team-build dev                 # automatic post-merge; builds from the default branch
/team-build dev --from hotfix/X # build from a specific branch (rare)
/team-build stage               # promotion build (if the project defines one)
/team-build prod                # honors config.build.prodPolicy
```

## Preconditions (all envs)
1. `<config.nonNegotiables>` loaded.
2. A build path is defined for this project — one of:
   - `config.build.buildCmd` (+ optional `authCmd`, `verifyCmd`), OR
   - `config.build.runbook` (a team-local runbook to follow), OR
   - the project deploys via `config.deploy.script` and has no separate image build (then `/team-build` is a no-op — direct the user to `/team-release`).
   If none is defined, STOP and tell the user the team config has no build path.
3. Version resolved into `$VERSION` from `config.versionSource`
   (`VERSION` file, `pyproject.toml`, `package.json`, or `composer.json`).

## Per-env flow

### prod — policy-gated
Read `config.build.prodPolicy`:
- `"refuse"` → emit the alert below and STOP. (Prod is CI-only; tagging the release is a source-control action, allowed with user approval.)
- any other value → follow `config.build.runbook` for prod, with explicit user confirmation.

```
🚨 NON_NEGOTIABLE_ALERT
Rule: <prod-build rule name from config.nonNegotiables>
No production build from a local workstation — prod is CI-only.
Path: verify the release branch is green → tag it → CI builds+pushes the prod artifact.
I won't build prod from this workstation. To trigger the tag+CI run, ask me to tag the release (source-control action, allowed with approval).
```

### dev / stage — run the configured build
Gates: clean working tree; source branch correct (default branch for dev unless
`--from`); last CI run for the SHA green (warn + ask if unknown); machine gate
green on HEAD (`config.machineGate.command`) unless `--skip-tests` AND CI was green.

Then execute the configured build. If `config.build.buildCmd` is set, run
(substituting `$REGISTRY`=`config.build.registry`, `$VERSION`):
```bash
# auth (if configured)
eval "${config.build.authCmd}"
# build + push
eval "${config.build.buildCmd}"
# verify (if configured)
eval "${config.build.verifyCmd}"
```
> zsh trap: always brace registry tags — `"${REGISTRY}:v${VERSION}"`, never
> `"$REGISTRY:v${VERSION}"` (unbraced `$var:x` triggers history modifiers).

If `config.build.runbook` is set instead of inline commands, follow that runbook
verbatim (it holds the team's registry/immutability/tag rules).

Verify + report:
```
✅ <env> build
  Source:   <branch> @ <sha>
  Artifact: <registry/tag or runbook-reported id>
  Version:  v${VERSION}
  Next:     deploy is a separate step — /team-release <env>
```

## Non-negotiables (by name — see config.nonNegotiables)
- **prod-build**: honor `config.build.prodPolicy`; never override a 🔴 rule via chat.
- **registry/IAM immutability**: don't mutate registry lifecycle, IAM, or keys during a build — just build and push.
- **no secrets in the artifact**: the build must not bake secrets/PII/test fixtures into the image.

## Failure modes
- **build tool missing** → instruct the user to install/enable it.
- **auth fails** → re-run `config.build.authCmd`; if the underlying credential/profile is missing, that's the blocker.
- **immutable tag already exists** → the version was already built; bump the version, don't force-delete the tag.
- **machine gate red on dev build** → DO NOT push; report and suggest `/team-work`.

## Integration
`/team-ship` invokes this automatically for `dev` after a successful merge.
