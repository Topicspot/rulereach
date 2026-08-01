# rulereach

Your agent instruction files can be perfectly written and still never reach the agent.
A Cursor rule with `globs` as a YAML list never attaches. A `@import` in `CLAUDE.md` that
points one directory too high is skipped without a word. A file in `.github/instructions/`
without `applyTo` applies to nothing. A nested `AGENTS.md` quietly replaces the root one.
None of that shows up as an error anywhere: the agent just works without your rules.

`rulereach` reads the instruction files in a repository, applies each tool's documented
loading rules, and reports what will never be loaded.

![rulereach demo](https://raw.githubusercontent.com/Topicspot/rulereach/main/assets/demo.gif)

```console
$ rulereach check
.claude/rules/api.md
  x RR204 [claude] paths pattern 'photos [2024/**' unreadable bracket expression, so it matches nothing
      fix: rewrite the pattern; escape a literal bracket as \[ and keep brace groups small
      docs: https://code.claude.com/docs/en/memory
.cursor/rules/style.mdc
  x RR102 [cursor] globs is a YAML list; Cursor expects one comma-separated string, so the rule never auto-attaches
      fix: write: globs: src/**/*.ts
      docs: https://forum.cursor.com/t/glob-pattern-rules-are-never-respected-by-agent/160133
AGENTS.md
  x RR201 [claude] the repository has AGENTS.md but no CLAUDE.md; Claude Code reads CLAUDE.md, not AGENTS.md, so it starts with no project instructions at all
      fix: add a CLAUDE.md whose first line is @AGENTS.md
      docs: https://code.claude.com/docs/en/memory

rulereach: 5 error(s), 4 warning(s), 1 note(s)
```

## Install

```bash
pipx install rulereach     # or: uv tool install rulereach
```

Nothing is sent anywhere: the tool reads files and exits. No API keys, no network calls.

## Use

```bash
rulereach check                 # report unreachable instructions, exit 1 on errors
rulereach check --strict        # exit 1 on warnings and notes too
rulereach check --tool cursor   # one tool at a time
rulereach check --exclude "tests/fixtures/**"   # skip deliberately broken fixtures
rulereach list                  # every instruction file and when it activates
rulereach explain src/app.ts    # what each tool loads when working on that file
```

`explain` is the answer to "why is the agent ignoring my rule":

```console
$ rulereach explain packages/web/index.ts
Working on packages/web/index.ts:

Codex CLI
  1. AGENTS.md - nearest file in the chain
  2. packages/web/AGENTS.md - nearest file in the chain

Claude Code
  (nothing - this tool loads no project instructions here)

Cursor
  1. AGENTS.md - AGENTS.md on the path to the file

GitHub Copilot
  1. packages/web/AGENTS.md - nearest AGENTS.md in the directory tree
```

Add `--json` to any command for machine-readable output.

## Checks

| ID | Tool | What it catches |
| --- | --- | --- |
| RR101 | Cursor | file in `.cursor/rules` that is not `.mdc`, so it is ignored |
| RR102 | Cursor | `globs` written as a YAML list or quoted, so nothing matches |
| RR103 | Cursor | rule with no `alwaysApply`, `globs` or `description`: manual only |
| RR104 | Cursor | `globs` pattern that matches no file in the repository |
| RR201 | Claude Code | `AGENTS.md` but no `CLAUDE.md`: no project instructions load |
| RR202 | Claude Code | `@import` that does not resolve (imports are relative to their file) |
| RR203 | Claude Code | import chain deeper than the four-hop limit |
| RR204 | Claude Code | `paths` pattern that cannot match: bad bracket, brace budget |
| RR205 | Claude Code | `paths` pattern that matches no file in the repository |
| RR206 | Claude Code | `claude.md` and other miscasings, ignored on case-sensitive filesystems |
| RR207 | Claude Code | non-`.md` file in `.claude/rules` |
| RR301 | Codex | `AGENTS.md` chain over the 32 KiB default cap, so the tail is dropped |
| RR302 | Copilot | nested `AGENTS.md` shadowing the root file for a subtree |
| RR303 | Codex | committed `AGENTS.override.md` hiding the shared `AGENTS.md` |
| RR304 | Codex | empty instruction file, which is skipped |
| RR401 | Copilot | file in `.github/instructions` not named `NAME.instructions.md` |
| RR402 | Copilot | path-specific instructions with no `applyTo`, so they never apply |
| RR403 | Copilot | `applyTo` pattern that matches no file in the repository |

Severity is about consequence, not style. An error means the file cannot load, ever. A
warning means it probably does not load, or loads less than you think. A note is behaviour
worth knowing that is not a mistake, such as one stale pattern in a rule whose other patterns
still match.

Every finding cites the vendor documentation that defines the behaviour. The exact
sentences the checks are built on are collected in [docs/semantics.md](docs/semantics.md).

## In CI

```yaml
- name: rulereach
  run: uvx rulereach check
```

`check` exits 1 when there is at least one error, 0 otherwise. Use `--strict` to fail on
warnings as well.

## What this is not

It does not sync your instruction files, and it does not grade your prose. Tools that
generate `CLAUDE.md` from `AGENTS.md` already exist, and so do linters for stale paths and
dead commands. `rulereach` answers the question they skip: will this file be loaded at all,
and when.

## Related

- [skillfrisk](https://github.com/Topicspot/skillfrisk) - scan agent skills and MCP servers
  for prompt injection and unsafe instructions.
- [ciparity](https://github.com/Topicspot/ciparity) - find drift between pre-commit hooks
  and your CI pipeline.

## License

MIT
