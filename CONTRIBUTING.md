# Contributing

Small, focused pull requests are welcome. Adding a check or a tool is the most useful thing
you can do here.

## Setup

```bash
uv sync --extra dev
uv run rulereach check tests/fixtures/broken
```

## The gate

```bash
bash scripts/check.sh
```

That runs ruff (format and lint), mypy in strict mode, pytest, vulture, pip-audit and
markdownlint. gitleaks and lychee run too when they are installed. CI runs the first four,
so a green `scripts/check.sh` means a green pull request.

## Adding a check

1. Find the sentence in the vendor's documentation that defines the behaviour and add it to
   `docs/semantics.md` with the link.
2. Implement the check in `src/rulereach/checks.py` with the next free ID, a severity, a
   one-line message that says what will not load, a fix hint, and the doc URL.
3. Add the failing case to a fixture under `tests/fixtures/` and assert on the ID.
4. Document the ID in the README table.

Errors are for "this cannot load, ever". Warnings are for "this probably does not load, or
loads less than you think". Notes are for behaviour worth knowing that is not a mistake.

## Adding a tool

Model the loading rules in `src/rulereach/tools.py` as a chain function, extend `Tool` and
discovery, and cite every rule in `docs/semantics.md`. A tool with guessed semantics is
worse than a missing tool, so leave out anything the documentation does not state.
