# Your AI agent shouldn't grade its own homework

*We just published team-mode, the multi-agent engineering workflow we run our own projects on, as an open Claude Code plugin. Here's what it does and why we built it this way.*

---

Anyone who has spent serious time with a coding agent knows the moment. The agent announces the work is done, the summary reads beautifully, and then you run the tests yourself and three of them fail. The agent wasn't lying, exactly. It just graded its own homework, and it grades generously.

We hit that moment enough times that we stopped treating it as a prompt problem and started treating it as a process problem. Human engineering teams solved this a long time ago: the person who wrote the code is not the person who approves the merge, "it works" means the CI is green and not that the author feels good about it, and the DBA gets to block a schema change even when everyone else is tired and wants to ship. None of that is about intelligence. It's about structure.

So we built that structure for Claude Code, ran our own projects through it, and this week we cleaned it up and published it. It's called **team-mode**, it's MIT licensed, and it installs in two commands:

```
/plugin marketplace add fuzemobi/claude-plugins
/plugin install team-mode@fuzemobi-plugins
```

## What it actually is

team-mode is 15 slash commands and 2 skills that run a full engineering flow: research, plan, work, review, ship, release. The work is done by a roster of role agents. Ours has a product owner, an architect, a lead developer, an implementer, a DBA, and a QA/security reviewer, but the roster is yours to define. Every project-specific detail lives in one config file: who votes, who can veto what, what command constitutes a passing build, which paths count as high risk, where the version number lives, how builds and deploys happen. The commands themselves hardcode nothing about your stack. Onboarding a new project is one config plus a two-line pointer file.

The flow looks like this. `/team-research` sends each agent off to investigate a problem independently and report back with evidence. Not vibes: a file and line number, a log line with a timestamp, a query result, a commit SHA. An opinion without an artifact doesn't count toward consensus. When the team converges (or fails to, three rounds max, then it escalates to you), `/team-plan` drafts a GitHub issue with a user story, acceptance criteria including a negative case, and a test-evidence plan. You approve the issue before it's created. `/team-work` runs the implementation in a git worktree with a TDD loop, `/team-ship` handles the version bump, PR, review, merge, tag, and cleanup, and `/team-release` runs migrations and deploys per your config.

That much is a nice workflow. Three specific rules are what make it work.

## Rule one: the machine gate outranks every vote

The consensus protocol has a step zero that runs before any completion vote is even tallied: the project's machine gate, whatever test-and-lint command you configured, must have produced its green exit line *in the current session transcript*. An agent that votes DONE without that line gets its vote counted as MORE_WORK, no matter how confident the reasoning sounded.

This is the single rule we'd defend hardest. Agent self-assessment is exactly the failure mode from the opening paragraph, and no amount of prompting fixes it as reliably as making the vote structurally invalid. Verification is the stop condition. Opinion is commentary.

## Rule two: vetoes are scoped to domains

Every agent's veto authority is a list in the config. The DBA can block a migration. The product owner can block a change to customer-visible output. Neither can block a logging refactor just because they feel strongly about it. A veto cast outside an agent's domain gets downgraded to "dig deeper" and noted in the record.

We added this after watching unscoped multi-agent setups drift into two bad states: either every agent rubber-stamps everything, or one loud agent blocks everything. Authority that comes from the config, not from confidence, keeps disagreement useful. The skill even names the anti-patterns it forbids, because they are easy to fall into without noticing: consensus theater (tuning prompts until the agents agree), vote buying (leaking one agent's vote to another mid-round), and silent escalation.

## Rule three: the worker never reviews its own diff

After the machine gate goes green, one fresh agent gets spawned with only the diff and the acceptance criteria. It never sees the reasoning that produced the code. Its job is adversarial: find the case where this diff breaks something the criteria promised. A real correctness gap reopens the loop. Style nitpicks and hypothetical edge cases that can't occur are explicitly out of scope, because a reviewer told to find problems will always find some, and chasing all of them is how you over-engineer a bug fix into a rewrite.

At merge time the review widens to five lenses running in parallel: code structure, database impact, architecture, security and coverage, and whether the thing actually satisfies the acceptance criteria. The implementer responds to comments but does not review their own work.

## The human stays in charge

Nothing in team-mode merges, releases, or touches production on its own. Issue creation waits for your approval. The merge gate prints its state and waits for an explicit answer, and an ambiguous reply gets asked again rather than interpreted charitably. When you do approve, the approval is recorded as a permanent comment on the PR with a timestamp and mode, so six months later you can see exactly who said yes to what. Production builds are refused outright under the default policy; prod belongs to CI.

There's also an honest concession to reality: a full council vote on a typo fix is theater. A lite lane exists for one-sentence, low-risk changes. It skips the vote. It never skips the machine gate or the refutation pass. The vote is negotiable; the verification is not.

## Two smaller things we're fond of

Context exhaustion is the quiet killer of long agent sessions, so handoffs in team-mode are structured documents, not hope. When an agent's context fills, it writes what it examined, what it found, and a next step concrete enough that a fresh agent can act immediately. The docs define "continue the investigation" as a failed handoff. "Open this file at this line and trace this branch" is a successful one.

And a small embarrassing one: while packaging the plugin, the validator caught that eight of our own command files had broken YAML frontmatter that had been silently dropping metadata. Publishing your tools means someone finally lints them. Recommended.

## What else is in the marketplace

team-mode shipped alongside two other plugins we extracted from our own toolbox. **doc-extract** does structural document extraction: headings, tables, reading order, and PDF form-field values instead of the character soup you get from naive PDF-to-text. **carrier-tower-research** builds cell-tower master lists for mobile carriers from FCC and international regulator data merged with crowdsourced RF observations, in a strict trust order with per-row provenance. Different domains, same underlying belief: the interesting part of agent tooling is the discipline, not the model.

Everything is at [github.com/fuzemobi/claude-plugins](https://github.com/fuzemobi/claude-plugins). The team-mode README includes the full command reference and an example config with the complete schema. Setup on a new project takes about ten minutes, most of which is the ten minutes you should have spent anyway writing down your non-negotiables. The plugin refuses to run without that file, and that's not a bug.

If you try it and something breaks, or your roster looks nothing like ours and you make it work anyway, open an issue on the repo. We're curious what other people's teams look like.
