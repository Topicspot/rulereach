# Loading semantics, with sources

Every check in `rulereach` is built on a sentence from a vendor's own documentation. This
page collects them so a finding can be checked instead of trusted. Verified 2026-08-01.

## Codex CLI

Source: [Project instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md)

- Global scope: in the Codex home directory, `AGENTS.override.md` if present, otherwise
  `AGENTS.md`. Only the first non-empty file at that level is used.
- Project scope: starting at the project root, Codex walks down to the current working
  directory. In each directory it checks `AGENTS.override.md`, then `AGENTS.md`, then the
  configured fallback names, and includes at most one file per directory.
- Merge order: files are concatenated from the root down, so files closer to the working
  directory come later and override earlier guidance.
- Empty files are skipped, and the chain stops once the combined size reaches
  `project_doc_max_bytes`, 32 KiB by default.

Checks: RR301 (chain over the cap), RR303 (committed override file), RR304 (empty file).

## Claude Code

Source: [Memory](https://code.claude.com/docs/en/memory)

- "Claude Code reads `CLAUDE.md`, not `AGENTS.md`." A repository that ships only
  `AGENTS.md` starts a Claude Code session with no project instructions. The documented fix
  is a `CLAUDE.md` that imports it with `@AGENTS.md`.
- Claude Code walks up the tree from the working directory, loading `CLAUDE.md` and
  `CLAUDE.local.md` in each directory along the way.
- `@path/to/file` imports are expanded at launch. Relative paths resolve against the file
  that contains the import, not the working directory. Imports nest up to four hops.
- Import parsing skips code spans and fenced blocks, so `` `@README` `` stays literal text.
- `.claude/rules/` holds `.md` files, discovered recursively. Without a `paths` field a rule
  loads unconditionally; with one it loads when Claude works on a matching file.
- `paths` patterns expand brace groups against a budget of 1000 expanded patterns. A pattern
  over the budget is used unexpanded, and its literal braces match no files.
- A `[` that cannot be read as a bracket expression, such as `photos [2024/**`, matches
  nothing; a literal bracket has to be escaped as `\[`.

Checks: RR201, RR202, RR203, RR204, RR205, RR206 (file name must be exactly `CLAUDE.md`,
which matters on case-sensitive filesystems), RR207.

## Cursor

Source: [Rules](https://cursor.com/docs/rules)

- Project rules live in `.cursor/rules` as `.mdc` files. "A plain `.md` file in
  `.cursor/rules` is ignored by the rules system because it has no frontmatter."
- Three frontmatter fields decide activation:

  | `alwaysApply` | `description` | `globs` | Behaviour |
  | --- | --- | --- | --- |
  | `true` | any | any | always included |
  | `false` | any | provided | attached when a matching file is in context |
  | `false` | provided | omitted | agent pulls it in by description |
  | `false` | omitted | omitted | only on an `@`-mention |

- `globs` takes several patterns as one comma-separated string. The documented examples are
  bare, unquoted values such as `docs/**/*.md, docs/**/*.mdx`. A YAML list or a quoted value
  is reported by users to stop matching:
  [forum thread](https://forum.cursor.com/t/glob-pattern-rules-are-never-respected-by-agent/160133).
  `rulereach` treats the list form as an error and the quoted form as a warning.
- Cursor also reads `AGENTS.md` as the simple alternative to `.cursor/rules`.

Checks: RR101, RR102, RR103, RR104.

## GitHub Copilot

Source: [Add repository instructions](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions)

- Repository-wide instructions live in `.github/copilot-instructions.md` and apply to every
  request in the repository.
- Path-specific instructions are `NAME.instructions.md` files within or below
  `.github/instructions`. The name must end with `.instructions.md`, and the frontmatter
  must contain `applyTo` with glob syntax; several patterns are separated by commas.
- When a path-specific file matches and the repository-wide file exists, both are used.
- `AGENTS.md` files can sit anywhere in the repository, and "the nearest `AGENTS.md` file in
  the directory tree will take precedence". A nested file therefore replaces the root file
  for its subtree rather than adding to it.

Checks: RR302, RR401, RR402, RR403.

## Deliberate omissions

Gemini CLI, Windsurf, Cline, Aider and Zed also read instruction files. They are not
modelled yet: a wrong model is worse than a missing one. Their loading rules are the natural
next scope, one tool per release, each with its citation added here.
