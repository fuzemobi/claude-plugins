---
name: team-atlas
description: 'Build or query the team atlas: a local code graph (graphify CLI, AST only, no API key) under tmp/graphify-out. Agents ask it for hubs, paths, and blast radius before opening files, so each reads only its slice. Optional; skipped when graphify is not installed.'
argument-hint: '[build | god-nodes | query "<question>" | path "<A>" "<B>" | affected "<symbol>"]'
allowed-tools: [Bash, Read]
model: sonnet
enabled: true
---

# /team-atlas

The atlas is team-mode's map of the codebase. It turns the paper idea of
"dynamic context" into something concrete: instead of loading architecture docs
into every prompt, an agent asks the atlas which files matter for its question
and reads only those.

It wraps the [`graphify`](https://pypi.org/project/graphifyy/) CLI. It never uses
the `/graphify` skill's default `graphify-out/` at the repo root. Everything goes
under `tmp/graphify-out/`, so `tmp/` must be gitignored.

## Preconditions

1. `command -v graphify` succeeds. If it doesn't, say "atlas skipped: graphify not
   installed (`uv tool install graphifyy`)" and stop. Nothing else in team-mode
   depends on the atlas.
2. `git check-ignore -q tmp/` succeeds. If `tmp/` is not ignored, stop and tell the
   user. The graph is local state and never gets committed.

## Usage

```
/team-atlas build                       # build or refresh (incremental)
/team-atlas god-nodes                   # the most connected files/symbols: start here
/team-atlas query "how is a batch sealed?"
/team-atlas path "Uploader" "S3Client"  # shortest path between two concepts
/team-atlas affected "seal_batch"       # what a change to this symbol can break
```

## Commands

```bash
G=tmp/graphify-out/graph.json

# build: local AST only. No API key, nothing leaves the machine. Incremental by default.
graphify extract . --code-only --out tmp

# orientation
graphify god-nodes --graph "$G" --top 10
graphify query "<question>" --graph "$G" --budget 1500
graphify path "<A>" "<B>" --graph "$G"
graphify affected "<symbol>" --graph "$G" --depth 2
```

`affected` and `path` need an exact node name (`No unique node match` means it
was ambiguous). Run `query` first and copy the name from its `NODE` lines, which
also give each node's file and line. If `$G` doesn't exist when a query runs, build first. Rebuild after a merge, or
when `/team-research` starts on a new issue. The incremental build only
re-extracts changed files.

## How the team uses it

- `/team-research`: each investigator runs `query` and `god-nodes` for its
  question, then reads only the files those point to.
- `/team-work`: before an edit, `affected` on the symbol being changed lists the
  callers the tests should cover.
- `/team-review`: each reviewer runs `affected` on changed symbols for blast radius.

## Rules

- **Orientation, not evidence.** A graph edge is a lead. A finding that tips a
  vote still cites a file and line number, a log line, or a query result.
- **Code-only by default.** `--code-only` keeps the build local and free. A full
  semantic extraction (docs, papers, LLM-inferred edges) sends content to an LLM
  backend, so the user has to ask for it.
- **Never commit `tmp/graphify-out/`.**
