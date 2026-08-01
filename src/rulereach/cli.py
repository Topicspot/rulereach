"""Command line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, checks, report
from .config import load_config
from .discovery import scan
from .model import Severity, Tool
from .tools import CHAINS

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rulereach",
        description=(
            "Check whether your agent instruction files can reach an agent at all: "
            "Codex, Claude Code, Cursor and GitHub Copilot."
        ),
    )
    parser.add_argument("--version", action="version", version=f"rulereach {__version__}")
    sub = parser.add_subparsers(dest="command")

    check = sub.add_parser("check", help="report instructions that never reach an agent")
    check.add_argument("path", nargs="?", default=".", help="repository root (default: .)")
    check.add_argument("--json", action="store_true", help="machine-readable output")
    check.add_argument("--strict", action="store_true", help="exit 1 on warnings and notes too")
    check.add_argument(
        "--exclude",
        action="append",
        metavar="GLOB",
        help="skip paths matching this glob, such as test fixtures (repeatable)",
    )
    check.add_argument(
        "--tool",
        action="append",
        choices=[tool.value for tool in Tool],
        help="limit the report to one tool (repeatable)",
    )

    listing = sub.add_parser("list", help="list instruction files and when they activate")
    listing.add_argument("path", nargs="?", default=".")
    listing.add_argument("--json", action="store_true")
    listing.add_argument("--exclude", action="append", metavar="GLOB")

    explain = sub.add_parser("explain", help="show the instruction chain for one file")
    explain.add_argument("target", help="repository-relative path you are about to work on")
    explain.add_argument("--path", default=".", help="repository root (default: .)")
    explain.add_argument("--json", action="store_true")
    explain.add_argument(
        "--tool",
        action="append",
        choices=[tool.value for tool in Tool],
        help="limit the output to one tool (repeatable)",
    )
    return parser


def _tools(selected: list[str] | None) -> list[Tool]:
    if not selected:
        return list(Tool)
    return [Tool(value) for value in selected]


def _root(path: str) -> Path:
    root = Path(path)
    if not root.is_dir():
        print(f"rulereach: not a directory: {path}", file=sys.stderr)
        raise SystemExit(EXIT_USAGE)
    return root


def _check(args: argparse.Namespace) -> int:
    root = _root(args.path)
    config = load_config(root)
    exclude = args.exclude if args.exclude is not None else (config.exclude or None)
    strict = args.strict or config.strict
    repo = scan(root, exclude)
    wanted = set(_tools(args.tool))
    findings = [finding for finding in checks.run(repo) if finding.tool in wanted]
    print(report.as_json(findings=findings) if args.json else report.format_findings(findings))
    if any(finding.severity is Severity.ERROR for finding in findings):
        return EXIT_FINDINGS
    if strict and findings:
        return EXIT_FINDINGS
    return EXIT_OK


def _list(args: argparse.Namespace) -> int:
    root = _root(args.path)
    config = load_config(root)
    exclude = args.exclude if args.exclude is not None else (config.exclude or None)
    repo = scan(root, exclude)
    print(report.as_json(sources=repo.sources) if args.json else report.format_inventory(repo))
    return EXIT_OK


def _explain(args: argparse.Namespace) -> int:
    root = _root(args.path)
    config = load_config(root)
    exclude = config.exclude or None
    repo = scan(root, exclude)
    target = Path(args.target)
    if target.is_absolute():
        try:
            target = target.relative_to(root.resolve())
        except ValueError:
            print(f"rulereach: {args.target} is outside {root}", file=sys.stderr)
            return EXIT_USAGE
    normalised = target.as_posix()
    chains = {tool: CHAINS[tool](repo, normalised) for tool in _tools(args.tool)}
    if args.json:
        print(report.as_json(chains=chains))
    else:
        print(report.format_explain(normalised, chains))
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "check":
        return _check(args)
    if args.command == "list":
        return _list(args)
    if args.command == "explain":
        return _explain(args)
    parser.print_help()
    return EXIT_USAGE


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
