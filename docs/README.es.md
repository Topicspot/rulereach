# rulereach

[English](../README.md) · [Русский](README.ru.md) · [简体中文](README.zh-CN.md) · **Español** · [Português](README.pt-BR.md)

[![PyPI](https://img.shields.io/pypi/v/rulereach?style=flat-square&label=pypi&color=3775A9)](https://pypi.org/project/rulereach/)
[![Python](https://img.shields.io/pypi/pyversions/rulereach?style=flat-square&color=4B8BBE)](https://pypi.org/project/rulereach/)
[![CI](https://github.com/Topicspot/rulereach/actions/workflows/ci.yml/badge.svg)](https://github.com/Topicspot/rulereach/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](https://github.com/Topicspot/rulereach/blob/main/LICENSE)

Tus archivos de instrucciones para el agente pueden estar perfectamente escritos y aun así no
llegar nunca al agente. Una regla de Cursor con `globs` como lista YAML no se adjunta jamás.
Un `@import` en `CLAUDE.md` que apunta un directorio más arriba se omite sin avisar. Un archivo
en `.github/instructions/` sin `applyTo` no aplica a nada. Un `AGENTS.md` anidado reemplaza en
silencio al de la raíz. Nada de esto aparece como error: el agente simplemente trabaja sin tus
reglas.

`rulereach` lee los archivos de instrucciones de un repositorio, aplica las reglas de carga
documentadas de cada herramienta e informa qué nunca se cargará.

![demo de rulereach](https://raw.githubusercontent.com/Topicspot/rulereach/main/assets/demo.gif)

## Instalación

```bash
pipx install rulereach     # o: uv tool install rulereach
```

No se envía nada a ningún sitio: la herramienta lee archivos y termina. Sin claves de API ni red.

## Uso

```bash
rulereach check                 # informa instrucciones inalcanzables, sale con 1 si hay errores
rulereach check --strict        # sale con 1 también con avisos y notas
rulereach check --tool cursor   # una herramienta a la vez
rulereach list                  # cada archivo de instrucciones y cuándo se activa
rulereach explain src/app.ts    # qué carga cada herramienta al trabajar en ese archivo
```

`explain` responde a la pregunta «por qué el agente ignora mi regla». Añade `--json` a
cualquier comando para una salida legible por máquinas.

## Qué se comprueba

18 comprobaciones para cuatro herramientas: Cursor (extensión `.mdc`, formato de `globs`, tipos
de activación), Claude Code (`AGENTS.md` sin `CLAUDE.md`, `@import` que no resuelve, límite de
cuatro saltos, patrones `paths`), Codex CLI (límite de 32 KiB en la cadena,
`AGENTS.override.md`, archivos vacíos) y GitHub Copilot (nombres `NAME.instructions.md`,
`applyTo` ausente, patrones muertos).

La severidad depende de la consecuencia, no del estilo: un error significa que el archivo no
puede cargarse nunca; un aviso, que probablemente no se carga o carga menos de lo que crees;
una nota, un comportamiento que conviene conocer. Cada hallazgo cita la documentación del
proveedor y las frases exactas están recogidas en [docs/semantics.md](semantics.md).

## En CI

```yaml
- name: rulereach
  run: uvx rulereach check
```

La documentación completa está en el [README en inglés](../README.md).
