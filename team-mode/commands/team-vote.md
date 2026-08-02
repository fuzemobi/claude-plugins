---
name: team-vote
description: 'Call a structured vote across the team on a specific question. Collects each voting member''s verdict, tallies per the consensus rule, reports result.'
argument-hint: '<research|completion|pr-review> [--question "<text>"]'
allowed-tools: [Read, Write, mcp__mempalace__mempalace_search, mcp__mempalace__mempalace_add_drawer, mcp__mempalace__mempalace_kg_add]
model: opus
enabled: true
---

# /team-vote

## Resource Efficiency

- **Memory:** Before tallying, search for prior votes: `mcp__mempalace__mempalace_search query="issue-<N> vote" wing="<config.memory.wing>"`. Write each tally with `mcp__mempalace__mempalace_add_drawer` + `mcp__mempalace__mempalace_kg_add`.
- **This skill runs on `opus`** for consensus synthesis.

## Usage
```
/team-vote research
/team-vote completion
/team-vote pr-review --question "Does this PR satisfy AC?"
```

## Procedure

### 1. Phase and question
- Phase from the first arg: `research` | `completion` | `pr-review`.
- Question: from `--question` or inferred from current context (Root Cause Brief for research; issue AC for completion; PR summary for pr-review).

### 2. Identify the domain in play
Map the question to a domain owner using `config.members[].vetoAuthority`. Typical shape:
- `config.impactVocabulary.customerImpact` / AC → **PO domain**
- system design / coupling / contracts → **architect domain**
- code structure / deps / logging → **lead-dev domain**
- schema / queries / partitions → **DBA domain**
- merge readiness / security → **QA/Sec domain**

The domain owner has a BINDING veto. Veto outside domain downgrades to DIG_DEEPER.

### 3. Conflict-of-interest check
If the question is in the **PO's veto domain**:
- Facilitator shifts to **lead-architect** (1st preference) or scrum-master persona (fallback).
- PO still casts a vote; just doesn't run the ceremony.

### 4. Collect votes
Ask each voting member for:
```json
{"agent":"<name>","phase":"<phase>","vote":"<verdict>","confidence":"High|Medium|Low","reasoning":"<one sentence>","concerns":[],"blockers":[]}
```

Verdicts per phase:
- research → CONSENSUS | DIG_DEEPER | VETO
- completion → DONE | MORE_WORK | VETO
- pr-review → APPROVE | REQUEST_CHANGES | BLOCK

### 5. Tally (apply from skills/team-mode/consensus.md)
- Votes with `blockers` non-empty downgrade to DIG_DEEPER/MORE_WORK/REQUEST_CHANGES.
- VETO/BLOCK honored only if agent has domain authority.
- **Consensus** = 5-of-6 positive + no valid domain-owner VETO.

### 6. Report
```
=== Team Vote — <phase> ===
Question: <text>
Domain: <customer-impact | schema | design | code | security>
Facilitator: <PO or lead-architect>

Tally:
- product-owner:    <verdict> (<conf>) — <one-liner>
- lead-architect:   <verdict> (<conf>) — <one-liner>
- lead-developer:   <verdict> (<conf>) — <one-liner>
- senior-developer: <verdict> (<conf>) — <one-liner>
- senior-dba:       <verdict> (<conf>) — <one-liner>
- qa-security:      <verdict> (<conf>) — <one-liner>

Result: CONSENSUS | NO_CONSENSUS | VETOED

Blockers: <list or none>
Disagreements: <summary>

Next: <proceed | loop round N+1 | escalate to user>
```

### 7. Save to memory
Use the memory backend (`config.memory`): `mcp__mempalace__mempalace_add_drawer wing="<config.memory.wing>" room="<config.memory.room>" name="issue-<N>-<phase>-vote-round-<N>"` — the full tally, for audit and for handoff continuity. Also `mcp__mempalace__mempalace_kg_add` the result as a fact: `(issue-<N>, vote-<phase>-round-<N>, <result>)`.

## Max rounds
- research: 3
- completion: 3
- pr-review: no hard limit (but warn at 3 — structural PR problem)

On round-3 with no consensus, STOP and escalate to user with agreements/disagreements summary.
