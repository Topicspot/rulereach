# rulereach

[English](../README.md) · [Русский](README.ru.md) · [简体中文](README.zh-CN.md) · [Español](README.es.md) · **Português**

[![PyPI](https://img.shields.io/pypi/v/rulereach?style=flat-square&label=pypi&color=3775A9)](https://pypi.org/project/rulereach/)
[![Python](https://img.shields.io/pypi/pyversions/rulereach?style=flat-square&color=4B8BBE)](https://pypi.org/project/rulereach/)
[![CI](https://github.com/Topicspot/rulereach/actions/workflows/ci.yml/badge.svg)](https://github.com/Topicspot/rulereach/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](https://github.com/Topicspot/rulereach/blob/main/LICENSE)

Seus arquivos de instruções para o agente podem estar perfeitamente escritos e ainda assim
nunca chegar ao agente. Uma regra do Cursor com `globs` como lista YAML nunca é anexada. Um
`@import` no `CLAUDE.md` que aponta um diretório acima é ignorado sem aviso. Um arquivo em
`.github/instructions/` sem `applyTo` não se aplica a nada. Um `AGENTS.md` aninhado substitui
silenciosamente o da raiz. Nada disso aparece como erro: o agente simplesmente trabalha sem as
suas regras.

O `rulereach` lê os arquivos de instruções do repositório, aplica as regras de carregamento
documentadas de cada ferramenta e informa o que nunca será carregado.

![demo do rulereach](https://raw.githubusercontent.com/Topicspot/rulereach/main/assets/demo.gif)

## Instalação

```bash
pipx install rulereach     # ou: uv tool install rulereach
```

Nada é enviado para lugar algum: a ferramenta lê arquivos e encerra. Sem chaves de API e sem rede.

## Uso

```bash
rulereach check                 # relata instruções inalcançáveis, sai com 1 em caso de erros
rulereach check --strict        # sai com 1 também para avisos e notas
rulereach check --tool cursor   # uma ferramenta por vez
rulereach list                  # cada arquivo de instruções e quando ele é ativado
rulereach explain src/app.ts    # o que cada ferramenta carrega ao trabalhar nesse arquivo
```

O `explain` responde à pergunta "por que o agente ignora a minha regra". Acrescente `--json` a
qualquer comando para uma saída legível por máquina.

## O que é verificado

18 verificações para quatro ferramentas: Cursor (extensão `.mdc`, formato de `globs`, tipos de
ativação), Claude Code (`AGENTS.md` sem `CLAUDE.md`, `@import` que não resolve, limite de quatro
saltos, padrões em `paths`), Codex CLI (limite de 32 KiB na cadeia, `AGENTS.override.md`,
arquivos vazios) e GitHub Copilot (nomes `NAME.instructions.md`, `applyTo` ausente, padrões
mortos).

A severidade vem da consequência, não do estilo: um erro significa que o arquivo nunca carrega;
um aviso, que provavelmente não carrega ou carrega menos do que você pensa; uma nota, um
comportamento que vale conhecer. Cada achado cita a documentação do fornecedor, e as frases
exatas estão reunidas em [docs/semantics.md](semantics.md).

## Em CI

```yaml
- name: rulereach
  run: uvx rulereach check
```

A documentação completa está no [README em inglês](../README.md).
