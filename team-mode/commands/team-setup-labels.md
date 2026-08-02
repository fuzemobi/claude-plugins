---
name: team-setup-labels
description: 'Create the GitHub workflow labels the team-mode commands expect (ready, in-progress, in-review, testing, pr-follow-up, blocked, needs-po-signoff, team-mode). Idempotent — safe to re-run; updates colors/descriptions if they drift. Run once per new repo.'
argument-hint: '[--repo OWNER/REPO] (optional — defaults to current git remote)'
allowed-tools: [Bash]
model: haiku
enabled: true
---

# /team-setup-labels

One-time setup: create the GitHub labels that team-mode commands use as workflow state markers.

## Usage

```
/team-setup-labels                         # current repo
/team-setup-labels --repo OWNER/REPO       # explicit
```

## Labels created

| Label | Color | Meaning |
|---|---|---|
| `ready` | green #0E8A16 | Research/planning complete; has AC; ready for `/team-work` |
| `in-progress` | amber #FBCA04 | Implementation underway on a branch |
| `in-review` | blue #0075CA | Code review / PR open |
| `testing` | teal #006B75 | QA / test-evidence pass |
| `pr-follow-up` | orange #D93F0B | Follow-up work identified during PR review |
| `blocked` | red #B60205 | Blocked on external dependency or decision |
| `needs-po-signoff` | purple #8957E5 | Customer-impacting change — requires product-owner blocking vote |
| `team-mode` | violet #5319E7 | Marker: this issue was processed through `/team-*` workflow |

## When to run

- **First time using team-mode in a repo** — run once.
- **After you notice label errors** in team-mode commands — re-run to heal.
- **Never needs manual intervention between runs** — it's idempotent.

The command runs `${CLAUDE_PLUGIN_ROOT}/scripts/setup_labels.sh`, which uses `gh label create` / `gh label edit --force` to make the label set match the spec.

## What it does NOT do

- Does not delete existing labels.
- Does not rename existing labels.
- Does not touch content-type labels (BUG, FEATURE, DOCUMENTATION) or priority labels (high-priority, etc.) — those are yours to manage.
- Does not apply labels to any issue; it only ensures the labels exist.

## Non-negotiables

- **Permissions rule**: creates labels via `gh` only — does not touch IAM, security groups, or other permissions.
- Safe to run without review.
