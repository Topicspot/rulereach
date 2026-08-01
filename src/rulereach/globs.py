"""Glob handling shared by every tool model.

The tools this package models all use shell-style globs over POSIX-style relative
paths, with two differences that matter in practice:

* Cursor and Copilot take several patterns as one comma-separated string.
* Claude Code expands brace groups and treats an unreadable ``[`` as a pattern that
  matches nothing.

Everything here works on strings, never on the filesystem, so it is cheap to test.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_EXPANDED_PATTERNS = 1000
"""Claude Code's brace-expansion budget for one ``paths`` list."""

_BRACE = re.compile(r"\{([^{}]*)\}")


@dataclass(frozen=True)
class Pattern:
    """One glob pattern plus whatever makes it unusable."""

    raw: str
    problem: str | None = None

    @property
    def usable(self) -> bool:
        return self.problem is None


def split_comma_patterns(value: str) -> list[str]:
    """Split a comma-separated glob string, keeping brace groups intact.

    ``docs/**/*.{md,mdx}, src/**`` is two patterns, not three.
    """
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for char in value:
        if char == "{":
            depth += 1
        elif char == "}":
            depth = max(0, depth - 1)
        if char == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    parts.append("".join(current))
    return [part.strip() for part in parts if part.strip()]


def expand_braces(pattern: str) -> list[str]:
    """Expand ``{a,b}`` groups the way Claude Code does, innermost group first."""
    match = _BRACE.search(pattern)
    if match is None:
        return [pattern]
    head, tail = pattern[: match.start()], pattern[match.end() :]
    alternatives = match.group(1).split(",")
    expanded: list[str] = []
    for alternative in alternatives:
        expanded.extend(expand_braces(f"{head}{alternative}{tail}"))
    return expanded


def _bracket_is_readable(pattern: str) -> bool:
    """Return False when a ``[`` cannot be read as a bracket expression."""
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "\\":
            index += 2
            continue
        if char == "[":
            closing = pattern.find("]", index + 2)
            if closing == -1:
                return False
            index = closing + 1
            continue
        index += 1
    return True


def analyse(patterns: list[str], *, expand: bool) -> list[Pattern]:
    """Turn raw pattern strings into :class:`Pattern` objects with problems attached.

    ``expand`` mirrors Claude Code, which expands brace groups against a budget. Cursor
    and Copilot pass their patterns to a matcher unexpanded, so they use ``expand=False``.
    """
    result: list[Pattern] = []
    budget = MAX_EXPANDED_PATTERNS
    for raw in patterns:
        if not _bracket_is_readable(raw):
            result.append(Pattern(raw, "unreadable bracket expression, so it matches nothing"))
            continue
        if not expand or "{" not in raw:
            result.append(Pattern(raw))
            continue
        variants = expand_braces(raw)
        if len(variants) > budget:
            result.append(
                Pattern(
                    raw,
                    f"expands to {len(variants)} patterns and blows the "
                    f"{MAX_EXPANDED_PATTERNS}-pattern budget, so the literal braces "
                    "match nothing",
                )
            )
            continue
        budget -= len(variants)
        result.append(Pattern(raw))
    return result


def to_regex(pattern: str) -> re.Pattern[str]:
    """Translate one glob into a regex anchored at both ends.

    ``**`` crosses directory separators, ``*`` and ``?`` do not, and a leading ``**/``
    also matches paths with no directory part at all.
    """
    out: list[str] = []
    index = 0
    length = len(pattern)
    while index < length:
        char = pattern[index]
        if char == "*":
            if pattern.startswith("**/", index):
                out.append("(?:[^/]+/)*")
                index += 3
                continue
            if pattern.startswith("**", index):
                out.append(".*")
                index += 2
                continue
            out.append("[^/]*")
            index += 1
            continue
        if char == "?":
            out.append("[^/]")
            index += 1
            continue
        if char == "[":
            closing = pattern.find("]", index + 2)
            if closing == -1:  # analyse() rejects these first; be safe anyway.
                out.append(re.escape(char))
                index += 1
                continue
            body = pattern[index + 1 : closing]
            if body.startswith("!"):
                body = "^" + body[1:]
            out.append(f"[{body}]")
            index = closing + 1
            continue
        if char == "\\" and index + 1 < length:
            out.append(re.escape(pattern[index + 1]))
            index += 2
            continue
        out.append(re.escape(char))
        index += 1
    return re.compile(f"^{''.join(out)}$")


def matches(pattern: str, path: str, *, expand: bool = True) -> bool:
    """Return True when ``path`` (repo-relative, POSIX separators) matches ``pattern``."""
    candidates = expand_braces(pattern) if expand and "{" in pattern else [pattern]
    return any(to_regex(candidate).match(path) for candidate in candidates)


def any_match(patterns: list[Pattern], path: str, *, expand: bool = True) -> bool:
    return any(matches(p.raw, path, expand=expand) for p in patterns if p.usable)
