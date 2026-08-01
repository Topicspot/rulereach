"""Find instruction files in a repository and read their frontmatter.

Discovery is deliberately pattern-based: it walks the tree once, skips the usual
dependency and build directories, and only looks at the paths the modelled tools read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .globs import Pattern, analyse, matches, split_comma_patterns
from .model import Kind, Source, Tool, When

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "target",
    "vendor",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "site-packages",
}

_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)
_FENCE = re.compile(r"^\s*(```|~~~)")
_IMPORT = re.compile(r"(?<![\w`])@([^\s`]+)")
_MISCASED = re.compile(r"^claude\.md$|^Claude\.md$|^CLAUDE\.MD$|^CLAUDE\.markdown$")


@dataclass
class Repo:
    """A repository scan: every instruction file found, plus the file inventory."""

    root: Path
    sources: list[Source]
    files: list[str]
    miscased: list[str]

    def of_tool(self, tool: Tool) -> list[Source]:
        return [source for source in self.sources if tool in source.tools]


def parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Split YAML frontmatter from the body. Malformed YAML yields an empty mapping."""
    match = _FRONTMATTER.match(text)
    if match is None:
        return {}, text
    try:
        loaded: Any = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return {}, text[match.end() :]
    data = loaded if isinstance(loaded, dict) else {}
    return data, text[match.end() :]


def find_imports(body: str) -> list[str]:
    """Collect ``@path`` imports, skipping code spans and fenced blocks.

    Claude Code ignores imports inside backticks and fences, so a path written as
    ``` `@README` ``` is documentation, not an import.
    """
    imports: list[str] = []
    in_fence = False
    for line in body.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        without_spans = re.sub(r"`[^`]*`", "", line)
        for match in _IMPORT.finditer(without_spans):
            target = match.group(1).rstrip(".,;:)")
            if target and not target.startswith(("http://", "https://")):
                imports.append(target)
    return imports


def _globs_field(frontmatter: dict[str, object], key: str) -> tuple[list[str], str | None, bool]:
    """Read a comma-separated glob field.

    Returns the patterns, the raw scalar as written, and whether the value was given in a
    form the tool does not parse (a YAML list, or a quoted pattern).
    """
    value = frontmatter.get(key)
    if value is None:
        return [], None, False
    if isinstance(value, list):
        raw = ", ".join(str(item) for item in value)
        return [str(item).strip() for item in value if str(item).strip()], raw, True
    text = str(value)
    return split_comma_patterns(text), text, False


def _cursor_when(
    frontmatter: dict[str, object],
) -> tuple[When, str, list[Pattern], str | None, bool]:
    always = frontmatter.get("alwaysApply") is True
    patterns, raw, as_list = _globs_field(frontmatter, "globs")
    description = str(frontmatter.get("description") or "").strip()
    if always:
        return When.ALWAYS, "alwaysApply: true", [], raw, as_list
    analysed = analyse(patterns, expand=False)
    if patterns:
        return When.PATH_SCOPED, "globs field is set", analysed, raw, as_list
    if description:
        return When.AGENT_REQUESTED, "agent selects it by description", [], raw, as_list
    return (
        When.MANUAL,
        "no alwaysApply, no globs, no description",
        [],
        raw,
        as_list,
    )


def _claude_rule_when(frontmatter: dict[str, object]) -> tuple[When, str, list[Pattern]]:
    value = frontmatter.get("paths")
    if value is None:
        return When.ALWAYS, "no paths frontmatter", []
    raw = (
        [str(item) for item in value]
        if isinstance(value, list)
        else split_comma_patterns(str(value))
    )
    return When.PATH_SCOPED, "paths frontmatter", analyse(raw, expand=True)


def _copilot_when(
    frontmatter: dict[str, object],
) -> tuple[When, str, list[Pattern], str | None, bool]:
    patterns, raw, as_list = _globs_field(frontmatter, "applyTo")
    if not patterns:
        return When.NEVER, "no applyTo frontmatter", [], raw, as_list
    if any(pattern == "**" for pattern in patterns):
        return When.ALWAYS, "applyTo: **", analyse(patterns, expand=False), raw, as_list
    return (
        When.PATH_SCOPED,
        "applyTo field is set",
        analyse(patterns, expand=False),
        raw,
        as_list,
    )


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _make(path: Path, root: Path, kind: Kind, tools: tuple[Tool, ...]) -> Source:
    text = _read(path)
    frontmatter, body = parse_frontmatter(text)
    return Source(
        path=path,
        relpath=path.relative_to(root).as_posix(),
        kind=kind,
        tools=tools,
        frontmatter=frontmatter,
        body=body,
        size=len(text.encode("utf-8")),
    )


def scan(root: Path, exclude: list[str] | None = None) -> Repo:
    """Walk ``root`` once and build a :class:`Repo`.

    ``exclude`` takes glob patterns relative to ``root``; matching paths are ignored, which is
    how a repository keeps its own test fixtures out of the report.
    """
    root = root.resolve()
    excluded = exclude or []
    files: list[str] = []
    sources: list[Source] = []
    miscased: list[str] = []

    for path in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if not path.is_file():
            continue
        relpath = path.relative_to(root).as_posix()
        if any(matches(pattern, relpath) for pattern in excluded):
            continue
        files.append(relpath)
        name = path.name
        parent = path.parent.relative_to(root).as_posix()

        if name == "AGENTS.md":
            sources.append(_make(path, root, Kind.AGENTS, (Tool.CODEX, Tool.CURSOR, Tool.COPILOT)))
        elif name == "AGENTS.override.md":
            sources.append(_make(path, root, Kind.AGENTS_OVERRIDE, (Tool.CODEX,)))
        elif name == "CLAUDE.md":
            sources.append(_make(path, root, Kind.CLAUDE_MD, (Tool.CLAUDE,)))
        elif name == "CLAUDE.local.md":
            sources.append(_make(path, root, Kind.CLAUDE_LOCAL, (Tool.CLAUDE,)))
        elif name == ".cursorrules":
            sources.append(_make(path, root, Kind.CURSOR_LEGACY, (Tool.CURSOR,)))
        elif relpath == ".github/copilot-instructions.md":
            sources.append(_make(path, root, Kind.COPILOT_REPO, (Tool.COPILOT,)))
        elif _MISCASED.match(name):
            miscased.append(relpath)
        elif f"/{parent}/".endswith("/.claude/rules/") or "/.claude/rules/" in f"/{relpath}":
            sources.append(_make(path, root, Kind.CLAUDE_RULE, (Tool.CLAUDE,)))
        elif "/.cursor/rules/" in f"/{relpath}":
            sources.append(_make(path, root, Kind.CURSOR_RULE, (Tool.CURSOR,)))
        elif parent.startswith(".github/instructions"):
            sources.append(_make(path, root, Kind.COPILOT_PATH, (Tool.COPILOT,)))

    for source in sources:
        _classify(source)

    return Repo(root=root, sources=sources, files=files, miscased=miscased)


def _classify(source: Source) -> None:
    """Fill in activation for one source, following its tool's documented rules."""
    if source.kind is Kind.CURSOR_RULE:
        if source.path.suffix != ".mdc":
            source.when, source.why = When.NEVER, "only .mdc files are read as project rules"
            return
        source.when, source.why, source.patterns, source.raw_globs, as_list = _cursor_when(
            source.frontmatter
        )
        if as_list:
            source.when, source.why = (
                When.NEVER,
                "globs given as a YAML list, not a comma-separated string",
            )
        return
    if source.kind is Kind.CLAUDE_RULE:
        if source.path.suffix != ".md":
            source.when, source.why = When.NEVER, "only .md files are read from .claude/rules"
            return
        source.when, source.why, source.patterns = _claude_rule_when(source.frontmatter)
        return
    if source.kind is Kind.COPILOT_PATH:
        if not source.path.name.endswith(".instructions.md"):
            source.when, source.why = When.NEVER, "file name does not end with .instructions.md"
            return
        source.when, source.why, source.patterns, source.raw_globs, _ = _copilot_when(
            source.frontmatter
        )
        return
    if source.kind in {Kind.CLAUDE_MD, Kind.CLAUDE_LOCAL}:
        source.imports = find_imports(source.body)
    source.when, source.why = When.ALWAYS, "loaded at session start"
