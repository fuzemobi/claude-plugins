#!/usr/bin/env python3
"""
Generate/refresh the project reference document by extracting:
  1. API routes (extractor chosen by config.docGen.extractRoutes)
  2. CLI commands (from `<config.docGen.cli>` help output)
  3. Architecture summary (preserves hand-written content)

Writes to <project>/PROJECT_REFERENCE.md with GENERATED blocks.
Hand-written content outside `<!-- generated:* -->` markers is preserved.

All project specifics (route extractor, scan roots, CLI command, version
source, project name) come from the team config, never hardcoded. Config is
resolved from `<project>/.claude/team.json` -> `~/.claude/teams/<name>/config.json`.

Usage:
    python sync_document.py                    # default output: PROJECT_REFERENCE.md
    python sync_document.py --dry-run          # show what would be generated
    python sync_document.py --out PATH
    python sync_document.py --section api      # only update API section
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---- team config resolution ----

def resolve_team_config(project_root: Path) -> dict:
    """Resolve the project's team config.

    Reads `<project>/.claude/team.json` (or a `team: <name>` line in
    `<project>/.claude/CLAUDE.md`) to find the team name, then loads
    `~/.claude/teams/<name>/config.json`. Returns {} if none is found so the
    caller can fall back to sensible defaults.
    """
    team_name = None
    team_json = project_root / ".claude" / "team.json"
    if team_json.exists():
        try:
            team_name = json.loads(team_json.read_text()).get("team")
        except (json.JSONDecodeError, OSError):
            team_name = None
    if not team_name:
        claude_md = project_root / ".claude" / "CLAUDE.md"
        if claude_md.exists():
            m = re.search(r"^team:\s*(\S+)", claude_md.read_text(), re.MULTILINE)
            if m:
                team_name = m.group(1)
    if not team_name:
        return {}
    config_path = Path.home() / ".claude" / "teams" / team_name / "config.json"
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


# ---- API route extraction ----
#
# Each extractor returns a list of normalized "route group" dicts:
#   {"name": str, "url_prefix": str|None, "file": Path,
#    "routes": [{"path", "methods", "function", "docstring", "line"}]}
# so a single renderer handles every stack.

def find_blueprints(root: Path) -> list[dict]:
    """Walk Python files under root, extract Flask Blueprint definitions + routes."""
    results = []
    for py in root.rglob("*.py"):
        if any(p in py.parts for p in ("venv", ".venv", "__pycache__", ".claude", "worktrees", "node_modules")):
            continue
        try:
            tree = ast.parse(py.read_text(), filename=str(py))
        except (SyntaxError, UnicodeDecodeError):
            continue

        # Find Blueprint(name, ...) assignments
        bp_vars = {}  # python_variable_name -> {name, url_prefix, file, routes}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                call = node.value
                is_bp = (
                    (isinstance(call.func, ast.Name) and call.func.id == "Blueprint") or
                    (isinstance(call.func, ast.Attribute) and call.func.attr == "Blueprint")
                )
                if is_bp:
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            bp_name = (
                                call.args[0].value
                                if call.args and isinstance(call.args[0], ast.Constant)
                                else target.id
                            )
                            url_prefix = None
                            for kw in call.keywords:
                                if kw.arg == "url_prefix" and isinstance(kw.value, ast.Constant):
                                    url_prefix = kw.value.value
                            bp_vars[target.id] = {
                                "name": bp_name,
                                "url_prefix": url_prefix,
                                "file": py,
                                "routes": [],
                            }

        # Find @<bp_var>.route(...) decorators on functions
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for deco in node.decorator_list:
                    if isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute):
                        if deco.func.attr == "route" and isinstance(deco.func.value, ast.Name):
                            bp_var = deco.func.value.id
                            if bp_var in bp_vars:
                                route_path = (
                                    deco.args[0].value
                                    if deco.args and isinstance(deco.args[0], ast.Constant)
                                    else "?"
                                )
                                methods = []
                                for kw in deco.keywords:
                                    if kw.arg == "methods" and isinstance(kw.value, ast.List):
                                        methods = [e.value for e in kw.value.elts if isinstance(e, ast.Constant)]
                                docstring = ast.get_docstring(node) or ""
                                bp_vars[bp_var]["routes"].append({
                                    "path": route_path,
                                    "methods": methods or ["GET"],
                                    "function": node.name,
                                    "docstring": docstring.split("\n")[0] if docstring else "",
                                    "line": node.lineno,
                                })

        for info in bp_vars.values():
            if info["routes"]:
                results.append(info)
    return results


def extract_laravel_routes(root: Path) -> list[dict]:
    """Extract routes from Laravel `routes/*.php` files, grouped by file.

    Laravel route definitions are PHP, not statically analyzable via `ast`, so
    this is a best-effort regex parse of `Route::<verb>(...)` / `Route::match(...)`
    calls. Handler names are captured when written as `Controller@method` or
    `[Controller::class, 'method']`.
    """
    routes_dir = root / "routes"
    if not routes_dir.exists():
        return []

    # Route::get('/path', ...) — an optional leading array arg (Route::match)
    # is skipped before the path string.
    verb_re = re.compile(
        r"Route::(get|post|put|patch|delete|options|any|match)\s*\(\s*"
        r"(?:\[[^\]]*\]\s*,\s*)?['\"]([^'\"]+)['\"]"
    )
    handler_str_re = re.compile(r"['\"]([A-Za-z0-9_\\]+@[A-Za-z0-9_]+)['\"]")
    handler_arr_re = re.compile(r"\[\s*([A-Za-z0-9_\\]+)::class\s*,\s*['\"]([A-Za-z0-9_]+)['\"]")

    groups = []
    for php in sorted(routes_dir.glob("*.php")):
        try:
            text = php.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        routes = []
        for i, line in enumerate(text.splitlines(), start=1):
            m = verb_re.search(line)
            if not m:
                continue
            verb, path = m.group(1), m.group(2)
            methods = ["ANY"] if verb in ("any", "match") else [verb.upper()]
            handler = ""
            hm = handler_str_re.search(line)
            if hm:
                handler = hm.group(1)
            else:
                hm = handler_arr_re.search(line)
                if hm:
                    handler = f"{hm.group(1)}@{hm.group(2)}"
            routes.append({
                "path": path if path.startswith("/") else "/" + path,
                "methods": methods,
                "function": handler or "?",
                "docstring": "",
                "line": i,
            })
        if routes:
            groups.append({
                "name": php.stem,
                "url_prefix": None,
                "file": php,
                "routes": routes,
            })
    return groups


def extract_api_groups(scan_roots: list[Path], extract_routes: str) -> list[dict]:
    """Dispatch to the configured route extractor. Returns normalized route groups."""
    groups: list[dict] = []
    if extract_routes == "flask":
        for root in scan_roots:
            groups.extend(find_blueprints(root))
    elif extract_routes == "laravel":
        for root in scan_roots:
            groups.extend(extract_laravel_routes(root))
    elif extract_routes == "express":
        # TODO: Express route extraction not implemented yet.
        pass
    elif extract_routes == "none":
        pass
    else:
        print(f"  warn: unknown extractRoutes '{extract_routes}'; no API routes extracted", file=sys.stderr)
    return groups


# ---- CLI extraction (parse help output of config.docGen.cli) ----

def extract_cli_commands(project_root: Path, cli: str | None) -> list[dict]:
    """Parse the help output of the configured CLI to extract the command list.

    `cli` is the full help-listing invocation from config.docGen.cli
    (e.g. "mycli --help", "php artisan list"). Calling the installed CLI follows
    the actual user-facing contract rather than reconstructing it from source.

    Returns a list of {name, section, help} dicts.
    """
    if not cli:
        return []

    argv = cli.split()
    prog = argv[0]
    try:
        result = subprocess.run(
            argv,
            capture_output=True, text=True, timeout=15, cwd=str(project_root),
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"  warn: could not run `{cli}` ({e}); CLI section will be empty", file=sys.stderr)
        return []
    if result.returncode != 0:
        print(f"  warn: `{cli}` exited {result.returncode}", file=sys.stderr)
        return []

    commands = []
    current_section = None
    in_examples = False

    # Section header: "Conversion Commands:" or "Database Commands:" at start of line
    section_re = re.compile(r"^([A-Z][\w /-]+):\s*$")
    # Command line: 2-4 leading spaces, word, 2+ spaces, description
    cmd_re = re.compile(r"^ {2,4}([a-z][a-z0-9:_-]*)\s{2,}(.+)$")

    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped == "Examples:":
            in_examples = True
            continue
        if in_examples:
            continue
        if stripped.startswith("#") or stripped.startswith(prog + " ") or stripped.startswith("Usage:"):
            continue

        m = section_re.match(line)
        if m and not line.startswith("    "):
            current_section = m.group(1).strip()
            continue

        m = cmd_re.match(line)
        if m and current_section:
            name, desc = m.group(1), m.group(2).strip()
            if name.startswith("-") or len(name) > 40:
                continue
            commands.append({
                "name": name,
                "section": current_section,
                "help": desc,
            })

    return commands


# ---- version detection ----

def get_version(root: Path, version_source: str) -> str:
    """Read the project version from the configured source.

    version_source is one of: VERSION | pyproject.toml | package.json | composer.json.
    """
    p = root / version_source
    if not p.exists():
        return "unknown"
    try:
        text = p.read_text()
    except OSError:
        return "unknown"

    if version_source == "VERSION":
        return text.strip() or "unknown"
    if version_source in ("package.json", "composer.json"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return "unknown"
        return str(data.get("version", "unknown"))
    if version_source == "pyproject.toml":
        m = re.search(r"^version\s*=\s*['\"]([^'\"]+)", text, re.MULTILINE)
        if m:
            return m.group(1)
    return "unknown"


# ---- rendering ----

def render_api_section(api_groups: list[dict], project_root: Path) -> str:
    if not api_groups:
        return "_No API routes found._\n"
    lines = []
    by_dir = {}
    for grp in api_groups:
        rel_dir = str(grp["file"].parent.relative_to(project_root))
        by_dir.setdefault(rel_dir, []).append(grp)

    for dir_, grps in sorted(by_dir.items()):
        lines.append(f"### `{dir_}/`\n")
        for grp in sorted(grps, key=lambda g: g["name"]):
            prefix = grp["url_prefix"] or ""
            rel_file = grp["file"].relative_to(project_root)
            lines.append(f"**`{grp['name']}`** (prefix: `{prefix or '(none)'}`) - `{rel_file}`\n")
            lines.append("| Method | Path | Handler | Description |")
            lines.append("|---|---|---|---|")
            for route in sorted(grp["routes"], key=lambda r: r["path"]):
                methods = ", ".join(route["methods"])
                full = (prefix or "") + route["path"]
                desc = route["docstring"][:80] if route["docstring"] else ""
                lines.append(f"| {methods} | `{full}` | `{route['function']}()` (L{route['line']}) | {desc} |")
            lines.append("")
    return "\n".join(lines)


def render_cli_section(commands: list[dict], cli: str | None) -> str:
    prog = cli.split()[0] if cli else "the CLI"
    if not commands:
        return (
            f"_No CLI commands extracted. Ensure `{prog}` is available in the active "
            f"environment, then re-run `/team-sync-document`._\n"
        )
    by_section = {}
    for cmd in commands:
        by_section.setdefault(cmd.get("section", "Other"), []).append(cmd)

    lines = []
    # Preserve the section order as discovered in the help output.
    for section in by_section:
        cmds = by_section[section]
        lines.append(f"### {section}\n")
        lines.append("| Command | Description |")
        lines.append("|---|---|")
        for cmd in sorted(cmds, key=lambda c: c["name"]):
            desc = cmd["help"][:100] if cmd["help"] else ""
            lines.append(f"| `{prog} {cmd['name']}` | {desc} |")
        lines.append("")
    return "\n".join(lines)


def render_stats(project_root: str, api_groups: list, commands: list, version: str) -> str:
    total_routes = sum(len(grp["routes"]) for grp in api_groups)
    return (
        f"- Version: **{version}**\n"
        f"- API route groups: **{len(api_groups)}** ({total_routes} routes)\n"
        f"- CLI commands: **{len(commands)}**\n"
        f"- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%MZ')}\n"
    )


# ---- file I/O with GENERATED blocks ----

def replace_generated_block(doc: str, section: str, new_content: str) -> str:
    """Replace content between `<!-- generated:START section -->` / `<!-- generated:END section -->`.
    Returns the doc unchanged if markers aren't present."""
    start = f"<!-- generated:START {section} -->"
    end = f"<!-- generated:END {section} -->"
    block = f"{start}\n{new_content.rstrip()}\n{end}"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if pattern.search(doc):
        return pattern.sub(block, doc, count=1)
    return doc


def build_template(project_name: str, cli: str | None) -> str:
    """Build the initial PROJECT_REFERENCE.md template for a new project.

    The title and CLI heading are derived from config so the template never
    names a specific project or stack.
    """
    prog = cli.split()[0] if cli else "CLI"
    cli_heading = f"## CLI Reference - `{prog}` commands"
    return f"""# Project Reference - {project_name}

**This document is partially auto-generated.** Content between `<!-- generated:START <section> -->` and `<!-- generated:END <section> -->` markers is overwritten by `/team-sync-document`. Everything else is hand-written and preserved.

<!-- generated:START stats -->
<!-- generated:END stats -->

## Architecture

See `docs/ARCHITECTURE.md` for the authoritative narrative. This page indexes the system surfaces (API, CLI) - the architecture section is hand-curated.

<!-- generated:START architecture -->
_(placeholder - hand-curated)_
<!-- generated:END architecture -->

## API Reference

API routes, extracted from source. Regenerated on every `/team-sync-document` run.

<!-- generated:START api -->
<!-- generated:END api -->

{cli_heading}

Extracted from the CLI help output. Regenerated on every `/team-sync-document` run.

<!-- generated:START cli -->
<!-- generated:END cli -->

## Critical Flows

_Hand-curated. Add or update when a flow crosses service or module boundaries, or touches a protected output surface._

## Non-Negotiables

See `./NON_NEGOTIABLES.md` - not regenerated here. Rule changes go through a PR against that file.
"""


# ---- main ----

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="PROJECT_REFERENCE.md")
    parser.add_argument("--root", default=".", help="project root (default: cwd)")
    parser.add_argument("--section", choices=["api", "cli", "stats", "all"], default="all")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    project_root = Path(args.root).resolve()
    out_path = project_root / args.out

    config = resolve_team_config(project_root)
    doc_gen = config.get("docGen", {})
    project_name = config.get("name") or project_root.name
    extract_routes = doc_gen.get("extractRoutes", "flask")
    cli = doc_gen.get("cli")
    version_source = config.get("versionSource", "VERSION")
    scan_dirs = doc_gen.get("scanRoots")

    print(f"project root: {project_root}")
    print(f"project name: {project_name}")
    print(f"output:       {out_path}")
    print(f"section:      {args.section}")
    print(f"routes:       {extract_routes}")
    print(f"cli:          {cli or '(none)'}")

    print("\nscanning…")
    if scan_dirs:
        scan_roots = [project_root / d for d in scan_dirs if (project_root / d).exists()]
        if not scan_roots:
            scan_roots = [project_root]
    else:
        scan_roots = [project_root]

    api_groups = extract_api_groups(scan_roots, extract_routes)
    commands = extract_cli_commands(project_root, cli)
    version = get_version(project_root, version_source)

    print(f"  {len(api_groups)} route groups ({sum(len(g['routes']) for g in api_groups)} routes)")
    print(f"  {len(commands)} CLI commands")

    if out_path.exists():
        doc = out_path.read_text()
    else:
        doc = build_template(project_name, cli)
        print("  (creating new doc from template)")

    sections_to_update = ["stats", "api", "cli"] if args.section == "all" else [args.section]

    if "stats" in sections_to_update:
        doc = replace_generated_block(doc, "stats", render_stats(project_root, api_groups, commands, version))

    if "api" in sections_to_update:
        doc = replace_generated_block(doc, "api", render_api_section(api_groups, project_root))

    if "cli" in sections_to_update:
        doc = replace_generated_block(doc, "cli", render_cli_section(commands, cli))

    if args.dry_run:
        print("\n--- DRY RUN, would write: ---")
        print(doc[:1200] + ("\n…" if len(doc) > 1200 else ""))
        print("--- end ---")
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc)
    print(f"\n✓ wrote {out_path} ({len(doc)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
