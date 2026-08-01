"""Per-tool loading models.

Each function answers one question: working on ``target`` in this repository, which
instruction files does this tool put in front of the model, in which order? The rules
come from each vendor's own documentation, cited in ``docs/semantics.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from .discovery import Repo
from .globs import any_match
from .model import Kind, Source, Tool, When

CODEX_MAX_BYTES = 32 * 1024
"""Codex's default ``project_doc_max_bytes``: the chain stops once it is reached."""


@dataclass
class Loaded:
    """One entry in a tool's effective instruction chain."""

    source: Source
    reason: str
    dropped: str | None = None


def _ancestors(target: str) -> list[str]:
    """Directories from the repository root down to the directory holding ``target``."""
    parts = PurePosixPath(target).parent.parts
    out = [""]
    for index in range(1, len(parts) + 1):
        out.append("/".join(parts[:index]))
    return out


def codex_chain(repo: Repo, target: str) -> list[Loaded]:
    """Codex concatenates one file per directory from the root down to the cwd."""
    chain: list[Loaded] = []
    used = 0
    for directory in _ancestors(target):
        override = _in_dir(repo, directory, Kind.AGENTS_OVERRIDE)
        agents = _in_dir(repo, directory, Kind.AGENTS)
        picked = override or agents
        if picked is None or not picked.body.strip():
            continue
        if used >= CODEX_MAX_BYTES:
            chain.append(
                Loaded(
                    picked,
                    "would come next in the chain",
                    dropped=f"chain already reached {CODEX_MAX_BYTES} bytes",
                )
            )
            continue
        reason = "override file wins in this directory" if override else "nearest file in the chain"
        chain.append(Loaded(picked, reason))
        used += picked.size
    return chain


def claude_chain(repo: Repo, target: str) -> list[Loaded]:
    """Claude Code walks up from the working directory, then adds ``.claude/rules``."""
    chain: list[Loaded] = []
    for directory in _ancestors(target):
        for kind in (Kind.CLAUDE_MD, Kind.CLAUDE_LOCAL):
            found = _in_dir(repo, directory, kind) or _in_dir(repo, _dot_claude(directory), kind)
            if found is not None:
                chain.append(Loaded(found, "memory file on the path to the working directory"))
    for source in repo.of_tool(Tool.CLAUDE):
        if source.kind is not Kind.CLAUDE_RULE:
            continue
        if source.when is When.NEVER:
            continue
        if source.when is When.ALWAYS:
            chain.append(Loaded(source, "rule without paths frontmatter"))
            continue
        if any_match(source.patterns, target, expand=True):
            chain.append(Loaded(source, "paths frontmatter matches the file"))
    return chain


def cursor_chain(repo: Repo, target: str) -> list[Loaded]:
    """Cursor loads always-on rules, matching globs, and AGENTS.md as the simple path."""
    chain: list[Loaded] = []
    for source in repo.of_tool(Tool.CURSOR):
        if source.kind is Kind.AGENTS and source.directory in _ancestors(target):
            chain.append(Loaded(source, "AGENTS.md on the path to the file"))
        elif source.kind is Kind.CURSOR_LEGACY:
            chain.append(Loaded(source, "legacy .cursorrules file"))
    for source in repo.of_tool(Tool.CURSOR):
        if source.kind is not Kind.CURSOR_RULE:
            continue
        if source.when is When.ALWAYS:
            chain.append(Loaded(source, "alwaysApply: true"))
        elif source.when is When.PATH_SCOPED and any_match(source.patterns, target, expand=False):
            chain.append(Loaded(source, "globs match the file"))
    return chain


def copilot_chain(repo: Repo, target: str) -> list[Loaded]:
    """Copilot combines the repo-wide file, the nearest AGENTS.md, and matching applyTo."""
    chain: list[Loaded] = []
    repo_wide = next(
        (source for source in repo.sources if source.kind is Kind.COPILOT_REPO),
        None,
    )
    if repo_wide is not None:
        chain.append(Loaded(repo_wide, "repository-wide custom instructions"))
    nearest = _nearest(repo, target, Kind.AGENTS)
    if nearest is not None:
        chain.append(Loaded(nearest, "nearest AGENTS.md in the directory tree"))
    for source in repo.of_tool(Tool.COPILOT):
        if source.kind is not Kind.COPILOT_PATH or source.when is When.NEVER:
            continue
        if source.when is When.ALWAYS or any_match(source.patterns, target, expand=False):
            chain.append(Loaded(source, "applyTo matches the file"))
    return chain


CHAINS = {
    Tool.CODEX: codex_chain,
    Tool.CLAUDE: claude_chain,
    Tool.CURSOR: cursor_chain,
    Tool.COPILOT: copilot_chain,
}


def _dot_claude(directory: str) -> str:
    return f"{directory}/.claude" if directory else ".claude"


def _in_dir(repo: Repo, directory: str, kind: Kind) -> Source | None:
    for source in repo.sources:
        if source.kind is kind and source.directory == directory:
            return source
    return None


def _nearest(repo: Repo, target: str, kind: Kind) -> Source | None:
    """The file of ``kind`` in the deepest directory on the path to ``target``."""
    for directory in reversed(_ancestors(target)):
        found = _in_dir(repo, directory, kind)
        if found is not None:
            return found
    return None
