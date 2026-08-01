"""Tests over fixture repositories, one per behaviour the tools document."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rulereach import checks, globs
from rulereach.cli import main
from rulereach.discovery import find_imports, parse_frontmatter, scan
from rulereach.model import Kind, Severity, Tool, When
from rulereach.tools import CODEX_MAX_BYTES, claude_chain, codex_chain, copilot_chain, cursor_chain

FIXTURES = Path(__file__).parent / "fixtures"
BROKEN = FIXTURES / "broken"
CLEAN = FIXTURES / "clean"
IMPORTS = FIXTURES / "imports"


def codes(root: Path) -> set[str]:
    return {finding.check for finding in checks.run(scan(root))}


# --- globs ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pattern", "path", "expected"),
    [
        ("src/**/*.ts", "src/a/b/app.ts", True),
        ("src/**/*.ts", "src/app.ts", True),
        ("src/**/*.ts", "lib/app.ts", False),
        ("**/*.py", "handler.py", True),
        ("**/*.py", "src/api/handler.py", True),
        ("*.md", "README.md", True),
        ("*.md", "docs/README.md", False),
        ("src/**", "src/a/b/c.txt", True),
        ("src/**/*.{ts,tsx}", "src/ui/a.tsx", True),
        ("tailwind.config.*", "tailwind.config.js", True),
    ],
)
def test_glob_matching(pattern: str, path: str, expected: bool) -> None:
    assert globs.matches(pattern, path) is expected


def test_comma_split_keeps_brace_groups() -> None:
    assert globs.split_comma_patterns("docs/**/*.{md,mdx}, src/**") == [
        "docs/**/*.{md,mdx}",
        "src/**",
    ]


def test_unreadable_bracket_is_flagged() -> None:
    analysed = globs.analyse(["photos [2024/**"], expand=True)
    assert analysed[0].problem is not None
    assert not analysed[0].usable


def test_brace_budget_is_enforced() -> None:
    huge = "{a,b}/{c,d}/{e,f}/{g,h}/{i,j}/{k,l}/{m,n}/{o,p}/{q,r}/{s,t}/*.ts"
    analysed = globs.analyse([huge], expand=True)
    assert analysed[0].problem is not None and "budget" in analysed[0].problem


# --- parsing -------------------------------------------------------------------------


def test_frontmatter_and_body() -> None:
    frontmatter, body = parse_frontmatter('---\napplyTo: "**/*.py"\n---\n\nText.\n')
    assert frontmatter == {"applyTo": "**/*.py"}
    assert body.strip() == "Text."


def test_malformed_frontmatter_falls_back_to_a_line_read() -> None:
    frontmatter, body = parse_frontmatter("---\nglobs: [unclosed\n---\nText.\n")
    assert frontmatter == {"globs": "[unclosed"}
    assert "Text." in body


def test_imports_skip_code_spans_and_fences() -> None:
    body = "@docs/a.md\n\nSee `@README` for details.\n\n```\n@not/an/import.md\n```\n@docs/b.md\n"
    assert find_imports(body) == ["docs/a.md", "docs/b.md"]


# --- discovery and activation --------------------------------------------------------


def test_inventory_of_the_broken_fixture() -> None:
    repo = scan(BROKEN)
    by_path = {source.relpath: source for source in repo.sources}
    assert by_path[".cursor/rules/legacy.md"].when is When.NEVER
    assert by_path[".cursor/rules/manual.mdc"].when is When.MANUAL
    assert by_path[".cursor/rules/style.mdc"].when is When.NEVER  # globs as a YAML list
    assert by_path[".github/instructions/tests.instructions.md"].when is When.NEVER
    assert by_path["AGENTS.md"].kind is Kind.AGENTS


def test_clean_fixture_activations() -> None:
    repo = scan(CLEAN)
    by_path = {source.relpath: source for source in repo.sources}
    assert by_path[".cursor/rules/style.mdc"].when is When.PATH_SCOPED
    assert by_path[".github/instructions/ts.instructions.md"].when is When.PATH_SCOPED
    assert by_path["CLAUDE.md"].imports == ["AGENTS.md"]


def test_skips_dependency_directories(tmp_path: Path) -> None:
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "AGENTS.md").write_text("noise\n")
    (tmp_path / "AGENTS.md").write_text("real\n")
    assert [source.relpath for source in scan(tmp_path).sources] == ["AGENTS.md"]


# --- checks --------------------------------------------------------------------------


def test_one_dead_pattern_among_live_ones_is_only_a_note(tmp_path: Path) -> None:
    rules = tmp_path / ".cursor" / "rules"
    rules.mkdir(parents=True)
    (tmp_path / "a.ts").write_text("export {};\n")
    (rules / "mixed.mdc").write_text("---\nglobs: **/*.ts, **/*.rb\n---\n\nRules.\n")
    findings = [finding for finding in checks.run(scan(tmp_path)) if finding.check == "RR104"]
    assert [finding.severity for finding in findings] == [Severity.NOTE]


def test_broken_fixture_findings() -> None:
    found = codes(BROKEN)
    assert {
        "RR101",
        "RR102",
        "RR103",
        "RR104",
        "RR201",
        "RR204",
        "RR302",
        "RR401",
        "RR402",
    } <= found


def test_clean_fixture_has_no_findings() -> None:
    assert checks.run(scan(CLEAN)) == []


def test_import_checks() -> None:
    findings = {finding.check: finding for finding in checks.run(scan(IMPORTS))}
    assert "RR202" in findings
    assert "missing.md" in findings["RR202"].message
    assert "RR206" in findings  # nested/claude.md is miscased
    assert findings["RR202"].severity is Severity.ERROR


def test_import_hint_points_at_the_real_path(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("text\n")
    (tmp_path / "CLAUDE.md").write_text("@guide.md\n")
    findings = [finding for finding in checks.run(scan(tmp_path)) if finding.check == "RR202"]
    assert findings and "docs/guide.md" in findings[0].hint


def test_codex_cap_is_reported(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("x" * (CODEX_MAX_BYTES + 10))
    findings = [finding for finding in checks.run(scan(tmp_path)) if finding.check == "RR301"]
    assert findings and findings[0].tool is Tool.CODEX


def test_override_file_is_reported(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("shared\n")
    (tmp_path / "AGENTS.override.md").write_text("mine\n")
    assert "RR303" in codes(tmp_path)


def test_every_finding_cites_documentation() -> None:
    for finding in checks.run(scan(BROKEN)):
        assert finding.doc.startswith("https://")
        assert finding.hint


# --- chains --------------------------------------------------------------------------


def test_codex_concatenates_from_the_root_down() -> None:
    repo = scan(BROKEN)
    chain = codex_chain(repo, "packages/web/index.ts")
    assert [entry.source.relpath for entry in chain] == ["AGENTS.md", "packages/web/AGENTS.md"]


def test_codex_drops_the_tail_over_the_cap(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("x" * (CODEX_MAX_BYTES + 1))
    nested = tmp_path / "pkg"
    nested.mkdir()
    (nested / "AGENTS.md").write_text("nested rules\n")
    chain = codex_chain(scan(tmp_path), "pkg/main.py")
    assert chain[-1].dropped is not None
    assert chain[-1].source.relpath == "pkg/AGENTS.md"


def test_copilot_uses_the_nearest_agents_file_only() -> None:
    repo = scan(BROKEN)
    chain = copilot_chain(repo, "packages/web/index.ts")
    paths = [entry.source.relpath for entry in chain]
    assert "packages/web/AGENTS.md" in paths
    assert "AGENTS.md" not in paths


def test_claude_loads_nothing_without_a_claude_file() -> None:
    assert claude_chain(scan(BROKEN), "src/app.ts") == []


def test_claude_chain_includes_matching_rules() -> None:
    chain = claude_chain(scan(IMPORTS), "src/main.rs")
    assert [entry.source.relpath for entry in chain] == ["CLAUDE.md", ".claude/rules/rust.md"]


def test_cursor_chain_skips_unreachable_rules() -> None:
    chain = cursor_chain(scan(BROKEN), "src/app.ts")
    assert [entry.source.relpath for entry in chain] == ["AGENTS.md"]


def test_cursor_chain_attaches_matching_globs() -> None:
    chain = cursor_chain(scan(CLEAN), "src/app.ts")
    assert [entry.source.relpath for entry in chain] == ["AGENTS.md", ".cursor/rules/style.mdc"]


# --- cli -----------------------------------------------------------------------------


def test_check_exit_codes(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", str(BROKEN)]) == 1
    assert "RR201" in capsys.readouterr().out
    assert main(["check", str(CLEAN)]) == 0
    assert "reach an agent" in capsys.readouterr().out


def test_strict_promotes_warnings(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", str(IMPORTS), "--tool", "codex"]) == 0
    capsys.readouterr()
    assert main(["check", str(BROKEN), "--tool", "copilot", "--strict"]) == 1
    capsys.readouterr()


def test_json_output_is_valid(capsys: pytest.CaptureFixture[str]) -> None:
    main(["check", str(BROKEN), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["counts"]["error"] > 0
    main(["list", str(BROKEN), "--json"])
    assert "sources" in json.loads(capsys.readouterr().out)
    main(["explain", "src/app.ts", "--path", str(BROKEN), "--json"])
    assert "chains" in json.loads(capsys.readouterr().out)


def test_explain_text_output(capsys: pytest.CaptureFixture[str]) -> None:
    main(["explain", "src/app.ts", "--path", str(BROKEN)])
    out = capsys.readouterr().out
    assert "Claude Code" in out
    assert "loads no project instructions here" in out


def test_list_output(capsys: pytest.CaptureFixture[str]) -> None:
    main(["list", str(CLEAN)])
    assert "AGENTS.md" in capsys.readouterr().out


def test_missing_directory_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["check", "/definitely/not/here"])
    assert excinfo.value.code == 2


def test_no_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 2
    assert "usage: rulereach" in capsys.readouterr().out


def test_exclude_skips_paths() -> None:
    repo = scan(FIXTURES.parent.parent, ["tests/fixtures/**"])
    assert all(not source.relpath.startswith("tests/fixtures/") for source in repo.sources)


def test_exclude_flag_on_the_cli(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", str(BROKEN), "--exclude", ".cursor/**"]) == 1
    out = capsys.readouterr().out
    assert "RR101" not in out
    assert "RR201" in out


def test_imports_stop_at_markdown_syntax() -> None:
    body = "- __[@docs/guide.md](docs/guide.md)__\n- @docs/other.md#section\n"
    assert find_imports(body) == ["docs/guide.md", "docs/other.md"]


def test_unquoted_star_glob_is_read_leniently() -> None:
    frontmatter, _ = parse_frontmatter("---\nglobs: **/*.test.ts\nalwaysApply: false\n---\nx\n")
    assert frontmatter["globs"] == "**/*.test.ts"


def test_lenient_rule_is_path_scoped(tmp_path: Path) -> None:
    rules = tmp_path / ".cursor" / "rules"
    rules.mkdir(parents=True)
    (tmp_path / "a.test.ts").write_text("export {};\n")
    (rules / "tests.mdc").write_text(
        "---\ndescription:\nglobs: **/*.test.ts\n---\n\nMock nothing.\n"
    )
    source = next(source for source in scan(tmp_path).sources if source.relpath.endswith(".mdc"))
    assert source.when is When.PATH_SCOPED
    assert checks.run(scan(tmp_path)) == []
