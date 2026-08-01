# rulereach

A CLI that reports agent instruction files which never reach an agent. Python, no runtime
dependencies beyond PyYAML.

## Commands

- `uv sync --extra dev` to set up.
- `bash scripts/check.sh` is the full gate and must pass before a commit.
- `uv run python -m pytest -q` for tests alone.

## Conventions

- Every check cites the vendor documentation that defines the behaviour, in
  `docs/semantics.md`. Never guess a tool's loading rules.
- Findings say what will not load, not how the file is written badly.
- Fixtures under `tests/fixtures/` are real directory trees; add a case there for every new
  check.
- Keep functions small and typed; mypy runs in strict mode.
