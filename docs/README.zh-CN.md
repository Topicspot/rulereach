# rulereach

[English](../README.md) · [Русский](README.ru.md) · **简体中文** · [Español](README.es.md) · [Português](README.pt-BR.md)

[![PyPI](https://img.shields.io/pypi/v/rulereach?style=flat-square&label=pypi&color=3775A9)](https://pypi.org/project/rulereach/)
[![Python](https://img.shields.io/pypi/pyversions/rulereach?style=flat-square&color=4B8BBE)](https://pypi.org/project/rulereach/)
[![CI](https://github.com/Topicspot/rulereach/actions/workflows/ci.yml/badge.svg)](https://github.com/Topicspot/rulereach/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](https://github.com/Topicspot/rulereach/blob/main/LICENSE)

即使智能体指令文件写得完美，它也可能永远到不了智能体手里。Cursor 规则里把 `globs` 写成 YAML
列表，规则就永远不会自动附加。`CLAUDE.md` 中指向上一级目录的 `@import` 会被静默跳过。
`.github/instructions/` 下缺少 `applyTo` 的文件不会应用到任何文件。嵌套的 `AGENTS.md` 会悄悄
取代根目录的那一个。这些都不会报错：智能体只是在没有你的规则的情况下工作。

`rulereach` 读取仓库中的指令文件，按各工具已公开的加载规则进行判断，并报告哪些内容永远不会被加载。

![rulereach 演示](https://raw.githubusercontent.com/Topicspot/rulereach/main/assets/demo.gif)

## 安装

```bash
pipx install rulereach     # 或者：uv tool install rulereach
```

不会发送任何数据：工具只读取文件然后退出。无需 API 密钥，不访问网络。

## 使用

```bash
rulereach check                 # 报告无法到达的指令，出现错误时退出码为 1
rulereach check --strict        # 警告和提示也会导致退出码 1
rulereach check --tool cursor   # 每次只检查一个工具
rulereach list                  # 列出所有指令文件及其激活条件
rulereach explain src/app.ts    # 处理该文件时每个工具会加载什么
```

`explain` 回答的正是「为什么智能体忽略了我的规则」。任何命令都可以加 `--json` 输出机器可读结果。

## 检查内容

覆盖四个工具的 18 项检查：Cursor（`.mdc` 扩展名、`globs` 格式、激活类型）、Claude Code
（有 `AGENTS.md` 却没有 `CLAUDE.md`、无法解析的 `@import`、四跳导入上限、`paths` 模式）、
Codex CLI（32 KiB 链上限、`AGENTS.override.md`、空文件）以及 GitHub Copilot
（`NAME.instructions.md` 命名、缺少 `applyTo`、失效模式）。

严重级别取决于后果，而不是风格：错误表示文件永远无法加载，警告表示很可能加载不了或加载得不完整，
提示表示值得了解但并非错误的行为。每条结论都引用厂商文档，具体原文收录在
[docs/semantics.md](semantics.md)。

## 在 CI 中

```yaml
- name: rulereach
  run: uvx rulereach check
```

完整文档见[英文 README](../README.md)。
