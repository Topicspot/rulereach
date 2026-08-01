"""Terminal and JSON output."""

from __future__ import annotations

import json
from collections.abc import Iterable

from .discovery import Repo
from .model import Finding, Severity, Source, Tool
from .tools import Loaded

MARK = {Severity.ERROR: "x", Severity.WARNING: "!", Severity.NOTE: "-"}


def format_findings(findings: list[Finding]) -> str:
    """Group findings by file, one line each, with the hint and the source of truth."""
    if not findings:
        return "rulereach: every instruction file can reach an agent."
    lines: list[str] = []
    current = ""
    for finding in findings:
        if finding.relpath != current:
            current = finding.relpath
            lines.append(current)
        lines.append(
            f"  {MARK[finding.severity]} {finding.check} [{finding.tool.value}] {finding.message}"
        )
        lines.append(f"      fix: {finding.hint}")
        lines.append(f"      docs: {finding.doc}")
    lines.append("")
    lines.append(summary(findings))
    return "\n".join(lines)


def summary(findings: Iterable[Finding]) -> str:
    counts = {severity: 0 for severity in Severity}
    for finding in findings:
        counts[finding.severity] += 1
    return (
        f"rulereach: {counts[Severity.ERROR]} error(s), "
        f"{counts[Severity.WARNING]} warning(s), {counts[Severity.NOTE]} note(s)"
    )


def format_inventory(repo: Repo) -> str:
    """List every instruction file with the tools that read it and when it activates."""
    if not repo.sources:
        return "rulereach: no agent instruction files found."
    lines = []
    width = max(len(source.relpath) for source in repo.sources)
    for source in sorted(repo.sources, key=lambda item: item.relpath):
        tools = ",".join(tool.value for tool in source.tools)
        lines.append(
            f"{source.relpath.ljust(width)}  {tools:<22} {source.when.value:<16} {source.why}"
        )
    return "\n".join(lines)


def format_explain(target: str, chains: dict[Tool, list[Loaded]]) -> str:
    """Show, per tool, the instruction chain for one file."""
    lines = [f"Working on {target}:"]
    for tool, chain in chains.items():
        lines.append("")
        lines.append(f"{tool.label}")
        active = [entry for entry in chain if entry.dropped is None]
        if not active:
            lines.append("  (nothing - this tool loads no project instructions here)")
        for index, entry in enumerate(active, start=1):
            lines.append(f"  {index}. {entry.source.relpath} - {entry.reason}")
        for entry in chain:
            if entry.dropped is not None:
                lines.append(f"  x  {entry.source.relpath} - dropped: {entry.dropped}")
    return "\n".join(lines)


def as_json(
    *,
    findings: list[Finding] | None = None,
    sources: list[Source] | None = None,
    chains: dict[Tool, list[Loaded]] | None = None,
) -> str:
    payload: dict[str, object] = {}
    if findings is not None:
        payload["findings"] = [finding.as_dict() for finding in findings]
        counts = {severity.value: 0 for severity in Severity}
        for finding in findings:
            counts[finding.severity.value] += 1
        payload["counts"] = counts
    if sources is not None:
        payload["sources"] = [
            {
                "path": source.relpath,
                "kind": source.kind.value,
                "tools": [tool.value for tool in source.tools],
                "activation": source.when.value,
                "why": source.why,
                "bytes": source.size,
            }
            for source in sources
        ]
    if chains is not None:
        payload["chains"] = {
            tool.value: [
                {
                    "path": entry.source.relpath,
                    "reason": entry.reason,
                    "dropped": entry.dropped,
                }
                for entry in chain
            ]
            for tool, chain in chains.items()
        }
    return json.dumps(payload, indent=2, sort_keys=True)
