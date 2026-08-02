#!/usr/bin/env bash
# Idempotently create the workflow labels the team-mode commands expect.
# Safe to re-run. Uses --force to update colors/descriptions if they drift.

set -euo pipefail

REPO="${1:-}"
if [[ -z "$REPO" ]]; then
  # Derive from git remote
  REPO=$(git remote get-url origin 2>/dev/null | sed -E 's|.*[:/]([^/]+/[^/]+)(\.git)?$|\1|' | sed 's|\.git$||')
  if [[ -z "$REPO" ]]; then
    echo "error: no --repo given and can't derive from git remote" >&2
    exit 1
  fi
fi

echo "Creating workflow labels in $REPO..."

# label: color (no #), description
declare -a LABELS=(
  "ready|0E8A16|Ready for implementation — research/planning complete, has AC"
  "in-progress|FBCA04|Implementation underway on a branch"
  "in-review|0075CA|In code review / PR open"
  "testing|006B75|QA / test-evidence pass"
  "pr-follow-up|D93F0B|Follow-up work identified during PR review"
  "blocked|B60205|Blocked on external dependency or decision"
  "needs-po-signoff|8957E5|Customer-impacting change — requires product-owner blocking vote"
  "team-mode|5319E7|Issue processed through /team-* workflow"
)

created=0
updated=0
failed=0
for entry in "${LABELS[@]}"; do
  IFS='|' read -r name color desc <<< "$entry"
  if gh label create "$name" --color "$color" --description "$desc" --repo "$REPO" 2>/dev/null; then
    created=$((created+1))
    echo "  + created: $name"
  else
    # Already exists — update via --force
    if gh label edit "$name" --color "$color" --description "$desc" --repo "$REPO" 2>/dev/null; then
      updated=$((updated+1))
      echo "  ~ updated: $name"
    else
      failed=$((failed+1))
      echo "  ! failed:  $name"
    fi
  fi
done

echo
echo "Summary: created=$created, updated=$updated, failed=$failed"
