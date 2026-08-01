# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[semantic versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-08-01

### Added

- Configuration file support: `[tool.rulereach]` in `pyproject.toml` or `.rulereach.toml` with
  `exclude` and `strict`, so the flags do not have to be repeated on every run. Command line
  flags still win, and `--no-strict` turns off a configured `strict`. Unusable files, keys and
  values are reported on stderr instead of being ignored.
  Thanks to [@HeaTTap](https://github.com/HeaTTap) for the original implementation in
  [#4](https://github.com/Topicspot/rulereach/pull/4).

## [0.1.0] - 2026-08-01

First release.

### Added

- `rulereach check`: 18 checks for instructions that never reach an agent, across Codex CLI,
  Claude Code, Cursor and GitHub Copilot. Exit 1 on errors, `--strict` to fail on warnings.
- `rulereach list`: every instruction file found, the tools that read it, and when it
  activates.
- `rulereach explain <file>`: the effective instruction chain per tool for one file,
  including entries dropped by Codex's 32 KiB cap.
- `--json` output on every command, `--tool` to narrow the report, and `--exclude` to skip
  paths such as test fixtures.
- `docs/semantics.md`: the documented behaviour each check is built on, with sources.

[0.2.0]: https://github.com/Topicspot/rulereach/releases/tag/v0.2.0
[0.1.0]: https://github.com/Topicspot/rulereach/releases/tag/v0.1.0
