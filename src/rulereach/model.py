"""Data model: what was found, when it activates, and what is wrong with it."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .globs import Pattern


class Tool(str, Enum):
    """A coding agent whose loading rules this package models."""

    CODEX = "codex"
    CLAUDE = "claude"
    CURSOR = "cursor"
    COPILOT = "copilot"

    @property
    def label(self) -> str:
        return {
            Tool.CODEX: "Codex CLI",
            Tool.CLAUDE: "Claude Code",
            Tool.CURSOR: "Cursor",
            Tool.COPILOT: "GitHub Copilot",
        }[self]


class Kind(str, Enum):
    """The role a file plays for its tool."""

    AGENTS = "AGENTS.md"
    AGENTS_OVERRIDE = "AGENTS.override.md"
    CLAUDE_MD = "CLAUDE.md"
    CLAUDE_LOCAL = "CLAUDE.local.md"
    CLAUDE_RULE = ".claude/rules"
    CURSOR_RULE = ".cursor/rules"
    CURSOR_LEGACY = ".cursorrules"
    COPILOT_REPO = "copilot-instructions.md"
    COPILOT_PATH = ".github/instructions"


class When(str, Enum):
    """How a file enters the context window."""

    ALWAYS = "always"
    PATH_SCOPED = "path-scoped"
    AGENT_REQUESTED = "agent-requested"
    MANUAL = "manual"
    NEVER = "never"

    @property
    def label(self) -> str:
        return {
            When.ALWAYS: "every session",
            When.PATH_SCOPED: "when a matching file is in play",
            When.AGENT_REQUESTED: "when the agent picks it by description",
            When.MANUAL: "only when @-mentioned",
            When.NEVER: "never",
        }[self]


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    NOTE = "note"


@dataclass
class Source:
    """One instruction file on disk, parsed but not yet judged."""

    path: Path
    relpath: str
    kind: Kind
    tools: tuple[Tool, ...]
    frontmatter: dict[str, object]
    body: str
    size: int
    when: When = When.ALWAYS
    why: str = ""
    patterns: list[Pattern] = field(default_factory=list)
    raw_globs: str | None = None
    imports: list[str] = field(default_factory=list)

    @property
    def directory(self) -> str:
        parent = str(Path(self.relpath).parent).replace("\\", "/")
        return "" if parent == "." else parent


@dataclass
class Finding:
    """One problem, tied to a file and to the documentation that defines the behaviour."""

    check: str
    severity: Severity
    relpath: str
    message: str
    hint: str
    doc: str
    tool: Tool

    def as_dict(self) -> dict[str, str]:
        return {
            "check": self.check,
            "severity": self.severity.value,
            "path": self.relpath,
            "tool": self.tool.value,
            "message": self.message,
            "hint": self.hint,
            "doc": self.doc,
        }
