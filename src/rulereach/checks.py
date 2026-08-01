"""The checks: every rule that says "this instruction will not reach the agent".

Each check cites the vendor documentation that defines the behaviour, so a finding can be
argued with rather than believed.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from .discovery import Repo
from .globs import matches
from .model import Finding, Kind, Severity, Source, Tool, When
from .tools import CODEX_MAX_BYTES

DOC_CURSOR = "https://cursor.com/docs/rules"
DOC_CLAUDE = "https://code.claude.com/docs/en/memory"
DOC_CODEX = "https://developers.openai.com/codex/guides/agents-md"
DOC_COPILOT = (
    "https://docs.github.com/en/copilot/how-tos/configure-custom-instructions"
    "/add-repository-instructions"
)
DOC_CURSOR_GLOBS = (
    "https://forum.cursor.com/t/glob-pattern-rules-are-never-respected-by-agent/160133"
)


def run(repo: Repo) -> list[Finding]:
    """Run every check over a scanned repository."""
    findings: list[Finding] = []
    findings += _cursor(repo)
    findings += _claude(repo)
    findings += _codex(repo)
    findings += _copilot(repo)
    findings.sort(key=lambda finding: (finding.relpath, finding.check))
    return findings


def _finding(
    check: str,
    severity: Severity,
    source_or_path: Source | str,
    tool: Tool,
    message: str,
    hint: str,
    doc: str,
) -> Finding:
    relpath = source_or_path if isinstance(source_or_path, str) else source_or_path.relpath
    return Finding(
        check=check,
        severity=severity,
        relpath=relpath,
        message=message,
        hint=hint,
        doc=doc,
        tool=tool,
    )


def _comma(source: Source) -> str:
    """The rule's patterns in the form Cursor parses: one comma-separated string."""
    return ", ".join(pattern.raw for pattern in source.patterns)


def _dead_patterns(source: Source, repo: Repo, *, expand: bool) -> tuple[list[str], Severity]:
    """Patterns that match nothing, and how much that matters.

    A rule whose every pattern is dead can never attach, which is a warning. A rule with one
    stale pattern among working ones still attaches, so it is only worth a note.
    """
    dead: list[str] = []
    live = 0
    for pattern in source.patterns:
        if not pattern.usable:
            continue
        if any(matches(pattern.raw, path, expand=expand) for path in repo.files):
            live += 1
        else:
            dead.append(pattern.raw)
    return dead, Severity.NOTE if live else Severity.WARNING


def _cursor(repo: Repo) -> list[Finding]:
    findings: list[Finding] = []
    for source in repo.sources:
        if source.kind is not Kind.CURSOR_RULE:
            continue
        if source.path.suffix != ".mdc":
            findings.append(
                _finding(
                    "RR101",
                    Severity.ERROR,
                    source,
                    Tool.CURSOR,
                    "file in .cursor/rules is not a .mdc file, so Cursor ignores it entirely",
                    "rename it to .mdc, or move the content to AGENTS.md",
                    DOC_CURSOR,
                )
            )
            continue
        if isinstance(source.frontmatter.get("globs"), list):
            findings.append(
                _finding(
                    "RR102",
                    Severity.ERROR,
                    source,
                    Tool.CURSOR,
                    "globs is a YAML list; Cursor expects one comma-separated string, so the "
                    "rule never auto-attaches",
                    f"write: globs: {_comma(source) or 'src/**/*.ts'}",
                    DOC_CURSOR_GLOBS,
                )
            )
        elif source.raw_globs and (source.raw_globs.startswith(('"', "'"))):
            findings.append(
                _finding(
                    "RR102",
                    Severity.WARNING,
                    source,
                    Tool.CURSOR,
                    "globs value is quoted; the quotes become part of the pattern and it stops "
                    "matching",
                    "remove the quotes: globs: src/**/*.ts",
                    DOC_CURSOR_GLOBS,
                )
            )
        if source.when is When.MANUAL:
            findings.append(
                _finding(
                    "RR103",
                    Severity.WARNING,
                    source,
                    Tool.CURSOR,
                    "rule has no alwaysApply, no globs and no description, so it only enters "
                    "context when you @-mention it",
                    "add alwaysApply: true, a globs pattern, or a description",
                    DOC_CURSOR,
                )
            )
        dead, severity = _dead_patterns(source, repo, expand=False)
        for pattern in dead:
            findings.append(
                _finding(
                    "RR104",
                    severity,
                    source,
                    Tool.CURSOR,
                    f"glob {pattern!r} matches no file in the repository",
                    "fix the pattern or delete the rule; as written it can never attach",
                    DOC_CURSOR,
                )
            )
    return findings


def _claude(repo: Repo) -> list[Finding]:
    findings: list[Finding] = []
    claude_files = [source for source in repo.sources if source.kind is Kind.CLAUDE_MD]
    agents_files = [source for source in repo.sources if source.kind is Kind.AGENTS]
    if agents_files and not claude_files:
        findings.append(
            _finding(
                "RR201",
                Severity.ERROR,
                agents_files[0],
                Tool.CLAUDE,
                "the repository has AGENTS.md but no CLAUDE.md; Claude Code reads CLAUDE.md, "
                "not AGENTS.md, so it starts with no project instructions at all",
                "add a CLAUDE.md whose first line is @AGENTS.md",
                DOC_CLAUDE,
            )
        )
    for relpath in repo.miscased:
        findings.append(
            _finding(
                "RR206",
                Severity.ERROR,
                relpath,
                Tool.CLAUDE,
                "file name is not exactly CLAUDE.md, so it is ignored on any case-sensitive "
                "filesystem, including CI",
                "rename it to CLAUDE.md",
                DOC_CLAUDE,
            )
        )
    for source in repo.sources:
        if source.kind in {Kind.CLAUDE_MD, Kind.CLAUDE_LOCAL}:
            findings += _claude_imports(repo, source)
        if source.kind is not Kind.CLAUDE_RULE:
            continue
        if source.path.suffix != ".md":
            findings.append(
                _finding(
                    "RR207",
                    Severity.WARNING,
                    source,
                    Tool.CLAUDE,
                    "only .md files are read from .claude/rules, so this file is ignored",
                    "rename it to .md",
                    DOC_CLAUDE,
                )
            )
            continue
        for pattern in source.patterns:
            if pattern.problem is not None:
                findings.append(
                    _finding(
                        "RR204",
                        Severity.ERROR,
                        source,
                        Tool.CLAUDE,
                        f"paths pattern {pattern.raw!r} {pattern.problem}",
                        "rewrite the pattern; escape a literal bracket as \\[ and keep brace "
                        "groups small",
                        DOC_CLAUDE,
                    )
                )
        dead_paths, severity = _dead_patterns(source, repo, expand=True)
        for dead in dead_paths:
            findings.append(
                _finding(
                    "RR205",
                    severity,
                    source,
                    Tool.CLAUDE,
                    f"paths pattern {dead!r} matches no file in the repository",
                    "fix the pattern or drop the paths field to load the rule unconditionally",
                    DOC_CLAUDE,
                )
            )
    return findings


def _claude_imports(repo: Repo, source: Source, *, depth: int = 1) -> list[Finding]:
    """Resolve ``@path`` imports relative to the importing file, following the 4-hop limit."""
    findings: list[Finding] = []
    base = source.path.parent
    for target in source.imports:
        if target.startswith("~"):
            continue  # Resolves in the user's home directory, outside the repository.
        resolved = (base / target).resolve()
        if not resolved.exists():
            findings.append(
                _finding(
                    "RR202",
                    Severity.ERROR,
                    source,
                    Tool.CLAUDE,
                    f"import @{target} does not resolve; imports are relative to the file that "
                    "contains them, and a miss is silent",
                    _import_hint(repo, source, target),
                    DOC_CLAUDE,
                )
            )
            continue
        if depth >= 4:
            findings.append(
                _finding(
                    "RR203",
                    Severity.WARNING,
                    source,
                    Tool.CLAUDE,
                    f"import @{target} sits more than four hops deep, past the import depth limit",
                    "flatten the import chain",
                    DOC_CLAUDE,
                )
            )
    return findings


def _import_hint(repo: Repo, source: Source, target: str) -> str:
    """Suggest the correct relative path when the file exists somewhere else."""
    name = PurePosixPath(target).name
    for candidate in repo.files:
        if PurePosixPath(candidate).name != name:
            continue
        try:
            relative = Path(candidate).resolve().relative_to(source.path.parent.resolve())
        except ValueError:
            up = _relative_to(source.path.parent, repo.root / candidate)
            return f"the file exists at {candidate}; write @{up}"
        return f"the file exists at {candidate}; write @{relative.as_posix()}"
    return "create the file or remove the import"


def _relative_to(base: Path, target: Path) -> str:
    base_parts = base.resolve().parts
    target_parts = target.resolve().parts
    common = 0
    while (
        common < min(len(base_parts), len(target_parts))
        and base_parts[common] == target_parts[common]
    ):
        common += 1
    up = [".."] * (len(base_parts) - common)
    return "/".join([*up, *target_parts[common:]])


def _codex(repo: Repo) -> list[Finding]:
    findings: list[Finding] = []
    total = 0
    for source in repo.sources:
        if source.kind is Kind.AGENTS_OVERRIDE:
            findings.append(
                _finding(
                    "RR303",
                    Severity.WARNING,
                    source,
                    Tool.CODEX,
                    "AGENTS.override.md is committed; Codex prefers it over AGENTS.md in the same "
                    "directory, so the shared file is ignored for everyone who checks this out",
                    "keep overrides out of the repository, or fold them into AGENTS.md",
                    DOC_CODEX,
                )
            )
        if source.kind is Kind.AGENTS:
            total += source.size
            if not source.body.strip():
                findings.append(
                    _finding(
                        "RR304",
                        Severity.WARNING,
                        source,
                        Tool.CODEX,
                        "instruction file is empty, and empty files are skipped",
                        "write the instructions or delete the file",
                        DOC_CODEX,
                    )
                )
    if total > CODEX_MAX_BYTES:
        findings.append(
            _finding(
                "RR301",
                Severity.WARNING,
                "AGENTS.md",
                Tool.CODEX,
                f"the AGENTS.md files total {total} bytes, over the {CODEX_MAX_BYTES}-byte default "
                "cap; on a deep chain the files nearest your work are the ones dropped",
                "trim the files, or raise project_doc_max_bytes in the Codex config",
                DOC_CODEX,
            )
        )
    return findings


def _copilot(repo: Repo) -> list[Finding]:
    findings: list[Finding] = []
    for source in repo.sources:
        if source.kind is not Kind.COPILOT_PATH:
            continue
        if not source.path.name.endswith(".instructions.md"):
            findings.append(
                _finding(
                    "RR401",
                    Severity.ERROR,
                    source,
                    Tool.COPILOT,
                    "path-specific instruction files must be named NAME.instructions.md; this one "
                    "is never loaded",
                    f"rename it to {source.path.stem}.instructions.md",
                    DOC_COPILOT,
                )
            )
            continue
        if source.when is When.NEVER:
            findings.append(
                _finding(
                    "RR402",
                    Severity.ERROR,
                    source,
                    Tool.COPILOT,
                    "no applyTo frontmatter, so the file matches no path and never applies",
                    'add frontmatter: applyTo: "**/*.py"',
                    DOC_COPILOT,
                )
            )
            continue
        dead, severity = _dead_patterns(source, repo, expand=False)
        for pattern in dead:
            findings.append(
                _finding(
                    "RR403",
                    severity,
                    source,
                    Tool.COPILOT,
                    f"applyTo pattern {pattern!r} matches no file in the repository",
                    "fix the pattern or delete the file",
                    DOC_COPILOT,
                )
            )
    nested = [source for source in repo.sources if source.kind is Kind.AGENTS and source.directory]
    if nested and any(
        source.directory == "" for source in repo.sources if source.kind is Kind.AGENTS
    ):
        for source in nested:
            findings.append(
                _finding(
                    "RR302",
                    Severity.NOTE,
                    source,
                    Tool.COPILOT,
                    "this nested AGENTS.md is the nearest file for everything under "
                    f"{source.directory}/, and Copilot uses the nearest file only, so the root "
                    "AGENTS.md does not apply there",
                    "repeat the rules that must hold everywhere, or keep one root file",
                    DOC_COPILOT,
                )
            )
    return findings
