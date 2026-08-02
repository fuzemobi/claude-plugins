# Consensus Protocol (sub-skill of team-mode)

Detailed tally logic for `/team-vote`. The main `SKILL.md` references this file for the specifics.

## Vote structure (every agent, every vote)

```json
{
  "agent": "<agent-name>",
  "phase": "research | completion | pr-review",
  "vote": "<phase-specific verdict>",
  "confidence": "High | Medium | Low",
  "reasoning": "<short explanation>",
  "concerns": ["<concern>", ...],
  "blockers": ["<blocker>", ...]
}
```

## Phase verdicts
| Phase      | Valid verdicts                            |
|------------|-------------------------------------------|
| research   | `CONSENSUS` / `DIG_DEEPER` / `VETO`       |
| completion | `DONE` / `MORE_WORK` / `VETO`             |
| pr-review  | `APPROVE` / `REQUEST_CHANGES` / `BLOCK`   |

## Tally logic (strict order)

### Step 0 — machine gate precedes the vote (completion phase only)
A `completion` vote ratifies a green build; it never substitutes for one. Before tallying a completion round:
- Confirm the project machine gate (`config.machineGate.command`, labelled `config.machineGate.label`) passed **in this session**. The green exit line must be present in the transcript.
- Any `DONE` vote cast without that green output is **invalid** and counts as `MORE_WORK` for tally purposes. State it: "agent voted DONE but no gate green in session — counting as MORE_WORK."
- If the gate is red or absent, the round is not eligible for consensus regardless of votes — loop.

This makes verification the agent runs (and re-reads) the stop condition, not agent opinion. The worker that produced the diff is not the one that grades it (see the refutation pass in `/team-work`).

### Step 1 — normalize blockers
Any vote with `blockers` non-empty is downgraded regardless of stated verdict:
- research: `CONSENSUS` → `DIG_DEEPER`
- completion: `DONE` → `MORE_WORK`
- pr-review: `APPROVE` → `REQUEST_CHANGES`

Blockers are objective. Agents may state APPROVE while listing a blocker — the blocker wins.

### Step 2 — validate veto authority
`VETO` / `BLOCK` is honored only if the agent has veto authority over the domain
in question. Veto authority is defined per agent in `config.members[].vetoAuthority`
— read it there (the orchestrator/scrum-master and the primary implementer
typically hold no veto). Outside-domain VETO → downgrade to
DIG_DEEPER/MORE_WORK/REQUEST_CHANGES and note the mismatch.

### Step 3 — identify the domain(s) in play
A single question may span multiple domains. Each domain owner's veto is binding within their lane. If a change touches two owners' domains at once (e.g. schema AND customer impact), both owners are domain owners for this vote.

### Step 4 — consensus rule
- **5-of-6 technical agents** agree on the positive verdict (`CONSENSUS` / `DONE` / `APPROVE`), AND
- **No valid VETO/BLOCK** from any domain owner on the domain in play.
- → consensus achieved.

### Step 5 — otherwise, loop
Not consensus. Next round with disagreements summarized.

## Tiebreakers

### 3-3 split (one abstains)
Treat as no consensus — loop.

### Domain conflict (two owners disagree)
Resolution: the owner of the domain more directly affected wins, per
`config.members[].vetoAuthority` (e.g. a schema question sits closer to the data
owner than the architect). When ambiguous → escalate to user.

### Lead vs implementer on structure
The lead/structure owner wins. The implementer implements.

### Business owner vs all others on "done" (customer-impact question)
The business owner wins on `config.impactVocabulary.customerImpact` questions.
Their veto is binding.

## Loop limits
- research: 3 rounds max. After 3 → escalate to user.
- completion: 3 rounds max. After 3 → escalate.
- pr-review: no hard limit. Warn at 3 — something structural is wrong with the PR.

## Anti-patterns (never)
- **Consensus theater** — adjusting prompts so agents agree. Disagreement is information.
- **Vote buying** — showing one agent another's vote mid-round. Each agent forms their view independently within a round.
- **Silent escalation** — if about to escalate, say so and why.
- **Silent override** — never downgrade a veto without stating "X voted VETO but domain is Y not their Z — downgrading to DIG_DEEPER."

## Output after tallying
Format in `/team-vote` step 6. Save to memory (backend per `config.memory`) at
`<config.memoryRoot>/<issue#>/<phase>/vote-round-<N>`.
