# rulereach

[English](../README.md) · **Русский** · [简体中文](README.zh-CN.md) · [Español](README.es.md) · [Português](README.pt-BR.md)

[![PyPI](https://img.shields.io/pypi/v/rulereach?style=flat-square&label=pypi&color=3775A9)](https://pypi.org/project/rulereach/)
[![Python](https://img.shields.io/pypi/pyversions/rulereach?style=flat-square&color=4B8BBE)](https://pypi.org/project/rulereach/)
[![CI](https://github.com/Topicspot/rulereach/actions/workflows/ci.yml/badge.svg)](https://github.com/Topicspot/rulereach/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](https://github.com/Topicspot/rulereach/blob/main/LICENSE)

Инструкции для агента можно написать идеально — и они всё равно не дойдут до агента.
Правило Cursor, где `globs` записан списком YAML, никогда не подключается. `@import` в
`CLAUDE.md`, указывающий на директорию выше нужной, молча пропускается. Файл в
`.github/instructions/` без `applyTo` не применяется ни к чему. Вложенный `AGENTS.md` тихо
заменяет корневой. Ошибки нигде не видно: агент просто работает без ваших правил.

`rulereach` читает файлы инструкций в репозитории, применяет документированные правила
загрузки каждого инструмента и показывает, что не будет загружено никогда.

![демо rulereach](https://raw.githubusercontent.com/Topicspot/rulereach/main/assets/demo.gif)

## Установка

```bash
pipx install rulereach     # или: uv tool install rulereach
```

Ничего никуда не отправляется: инструмент читает файлы и завершает работу. Без ключей и без сети.

## Использование

```bash
rulereach check                 # отчёт о недостижимых инструкциях, код возврата 1 при ошибках
rulereach check --strict        # код 1 также при предупреждениях и заметках
rulereach check --tool cursor   # по одному инструменту
rulereach list                  # все файлы инструкций и условия их активации
rulereach explain src/app.ts    # что каждый инструмент загрузит при работе с этим файлом
```

`explain` отвечает на вопрос «почему агент игнорирует моё правило». Добавьте `--json` к любой
команде для машинного вывода.

## Что проверяется

18 проверок для четырёх инструментов: Cursor (`.mdc`, формат `globs`, типы активации),
Claude Code (`AGENTS.md` без `CLAUDE.md`, нерешаемые `@import`, лимит в четыре перехода,
шаблоны `paths`), Codex CLI (лимит 32 KiB на цепочку, `AGENTS.override.md`, пустые файлы) и
GitHub Copilot (имена `NAME.instructions.md`, отсутствующий `applyTo`, мёртвые шаблоны).

Строгость определяется последствием, а не стилем: ошибка — файл не загрузится никогда,
предупреждение — скорее всего не загрузится или загрузится не полностью, заметка — поведение,
о котором стоит знать. Каждая находка ссылается на документацию вендора; конкретные цитаты
собраны в [docs/semantics.md](semantics.md).

## В CI

```yaml
- name: rulereach
  run: uvx rulereach check
```

Полная документация — в [английском README](../README.md).
