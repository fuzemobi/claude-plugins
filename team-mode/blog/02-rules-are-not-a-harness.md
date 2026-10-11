# Rules Are Not a Harness

*Part 2 on agentic engineering. Forty-six rules, two hooks nobody installed, and what Google's new SDLC paper gets right about running a team of coding agents.*

---

In August we published team-mode, the multi-agent workflow we run our own projects on, with one idea at its center: your AI agent shouldn't grade its own homework. This week I went back and audited the codebase that has leaned on it hardest, a telecom billing pipeline we build and run for our outsourcing partner. I expected to find gaps in the agents. I found gaps in us.

The repo has 1,858 commits. 601 of them start with "fix". 539 carry a Claude co-author trailer. Next to the code sits a NON_NEGOTIABLES file with 46 numbered rules, and almost every one of them has an incident behind it. And in `.claude/hooks/` there were two small scripts: one that refuses to let an agent end its turn while the billing golden tests are red, and one that blocks the single most dangerous command this project has ever run.

Neither script was registered in any settings file. They had never run once.

## Two articles, one pattern

Two pieces crossed my desk the same week, and they read like a diagnosis of that repo.

The first was a write-up of Google's whitepaper *The New SDLC With Vibe Coding* by Addy Osmani, Shubham Saboo, and Sokratis Kartakis, which went out as Day 1 reading for Google's AI Agents Intensive on Kaggle in June. Its central claim is that the line between vibe coding and agentic engineering is verification. Not the model, not the prompt, not the tool. If nothing checks the output deterministically and nothing checks how the agent got there, you are vibe coding, however elaborate the setup looks. It also reframes the agent as model plus harness: the prompts, tools, context, sandboxes, and guardrails around the model. The harness is the team's job, and it usually matters more than the model.

The second was Abul Kalam Azad's "The Vibe Coding Trap" in Level Up Coding, aimed at founders shipping AI-built MVPs. The part that stuck with me is what he calls the re-prompting paradox. A bug appears, the error goes back into the chat, and the model patches the symptom it can see, often by quietly removing a guard or disabling a check. The patch works. Something else breaks. Repeat until nobody can audit the code.

I've seen founders treat that as a beginner's problem. It isn't. We had a full workflow, a test gate, a council of reviewing agents, and a human approving every merge. We still lived inside that loop for months. We just had a better word for each turn of it: a rule.

## What the loop looked like for us

A few real entries from our incident log, with our partner's details taken out:

- A database reset command meant for development was run against production and wiped months of billing history. That became Rule 0, "permanently banned," written in bold at the top of the project instructions.
- A common shell idiom, `grep -q` at the end of a pipe under `set -o pipefail`, silently inverted two safety checks in one day. One nightly batch skipped every step it was supposed to run and still reported COMPLETE. The first fix patched one instance. The pattern came back somewhere else, so the rule now says to sweep the whole script.
- An agent parallelized a job that has to run one at a time. It burned 25 sequence numbers and delivered zero files.
- An agent asked to fix one line returned a reformatted, renamed, "improved" file in which the actual fix couldn't be reviewed. That became Rule 43, strict patch mode.
- Eventually we deleted 219 files and 60,364 lines in one pruning commit. The note in our instructions says it plainly: the files were the defect.

Every one of those incidents ended with a paragraph added to an instruction file. Each paragraph was correct. Together they became their own problem: every session in that repo now loads around 1,350 lines of instructions before it reads a single line of code. The Google paper has a name for this. Static context is paid for on every call, and too much of it buries the rules that matter under the ones that don't.

And here is the uncomfortable part. A rule in a markdown file is a request. The agent can skim it, weigh it against a user who sounds in a hurry, or lose it in a long context. The two hooks were the opposite: deterministic, cheap, and impossible to talk past. We wrote them and never wired them up, so our most important rule was enforced by a sentence.

## The harness is where the leverage is

The best public evidence for the harness argument comes from LangChain. They took their coding agent from 52.8 to 66.5 on Terminal Bench 2.0, outside the top 30 to the top 5, without touching the model. One of the changes that mattered was a middleware that stops the agent right before it declares itself finished and forces a verification pass. That is almost exactly the Stop hook sitting unregistered in our repo.

(One note if you read the Medium summary of the Google paper: it presents the Terminal Bench jump and the 13.7-point LangChain gain as two separate data points. They're the same experiment.)

The other lesson from our log is that the strongest guardrail is often removing the capability. Rule 0 stopped being a worry on the day the reset command was deleted from the CLI. A banned command that no longer exists can't be run by accident, by a tired human, or by an agent that read the rule and decided this case was different.

## What we changed in team-mode 1.1

We took that audit and turned it into the next release of the plugin. The changes are small on purpose.

- **The gate has to be wired, not just written.** At session start, team-mode checks whether your machine gate actually runs from a Stop hook, and whether any script in `.claude/hooks/` is sitting there unregistered. If so, it tells you once.
- **No gate, no delegation.** If a project has no machine gate, `/team-work` won't run autonomously. It says so and works one reviewed change at a time. Handing work to agents without a way to verify it is the paper's definition of vibe coding at scale.
- **Trajectory notes.** Before review, the implementer writes down the assumptions it made that the plan didn't state, any files it touched outside the plan, and any acceptance criteria it couldn't test. The fresh-context reviewer checks that note against the issue. This is a cheap version of the paper's trajectory evaluation, and it targets the 80-percent-looks-right failure directly: a green test suite on the wrong reading of the problem.
- **Assumptions in the plan.** Every issue now carries an "Assumptions and edge cases" section and a list of files expected to change, so there's something concrete to compare the trajectory against.
- **A two-minute harness retro on every ship.** After merge, the scrum-master names the one harness gap that caused the most rework and proposes one fix, preferring a hook, a test, or a config value over more prose. The human approves it. That is how the incident-to-rule loop turns into an incident-to-enforcement loop.
- **KISS as a tool.** team-mode now depends on ponytail, an open-source plugin that pushes the agent toward the smallest solution that works without cutting validation, error handling, or security. Its own benchmark shows a date picker dropping from 404 lines to 23. Our Rules 43 and 44 were ponytail written in prose. Now the implementer works with it on, a ponytail review is one of the review lenses, and deliberate shortcuts get listed in the PR as debt instead of disappearing.
- **An atlas instead of a wall of docs.** A new `/team-atlas` command builds a local code graph with the graphify CLI, using only the syntax tree, with no API calls. On our billing repo it built 5,847 nodes and 10,010 edges in about six seconds. Agents ask it which files matter for their question and read those, instead of loading architecture documents into every prompt.

## Three questions for your own setup

You don't need our plugin to use any of this. If you run coding agents on anything that matters, three questions will tell you most of what you need to know.

1. Is your test gate a hook, or a sentence? If the agent can end its turn with the suite red, you're relying on it to want to run the tests.
2. Does anything check the path, or only the output? An agent that misunderstood the problem can still pass every test you wrote for the wrong problem.
3. When something breaks, what does the fix leave behind? If the answer is usually another paragraph in an instruction file, you're paying interest on the same debt the founders in Azad's article are paying. They just get the bill sooner.

We had good rules. What we didn't have, until this week, was a harness that made them true.

team-mode 1.1 is MIT licensed and installs from our marketplace:

```
/plugin marketplace add DietrichGebert/ponytail
/plugin marketplace add fuzemobi/claude-plugins
/plugin install team-mode@fuzemobi-plugins
```

The full source, including both articles in this series, is at github.com/fuzemobi/claude-plugins.

---

Sources: Addy Osmani, Shubham Saboo, Sokratis Kartakis, *The New SDLC With Vibe Coding* (Google, 2026). Mehmet Özel, "Google's New SDLC Guide Draws a Hard Line Between Vibe Coding and Agentic Engineering," Data Science Collective (June 26, 2026). Abul Kalam Azad, "The Vibe Coding Trap: Why AI-Generated MVPs Are Quietly Bankrupting Early-Stage Startups," Level Up Coding (September 25, 2026). LangChain, "Improving Deep Agents with harness engineering" (February 2026). Dietrich Gebert, ponytail README and agentic benchmark (github.com/DietrichGebert/ponytail). Part 1 of this series: "Your AI Agent Shouldn't Grade Its Own Homework" (August 2, 2026).
