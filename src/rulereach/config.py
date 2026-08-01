"""Project level configuration, so that flags do not have to be repeated on every run.

Two files are read from the repository root: ``[tool.rulereach]`` in ``pyproject.toml``
and top level keys in ``.rulereach.toml``. The dedicated file wins over ``pyproject.toml``,
and command line flags win over both. Anything that cannot be used is reported on stderr:
a tool about instructions that silently fail must not fail silently itself.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):  # pragma: no cover - version specific import
    import tomllib
else:  # pragma: no cover - version specific import
    import tomli as tomllib

KEYS = ("exclude", "strict")


@dataclass(frozen=True)
class Config:
    """Settings read from a file. ``None`` means "not set", so flags can override."""

    exclude: list[str] | None = None
    strict: bool | None = None
    source: str | None = None


def _warn(message: str) -> None:
    print(f"rulereach: {message}", file=sys.stderr)


def _read(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        with path.open("rb") as handle:
            data: dict[str, Any] = tomllib.load(handle)
            return data
    except tomllib.TOMLDecodeError as error:
        _warn(f"ignoring {path.name}: invalid TOML ({error})")
    except OSError as error:
        _warn(f"ignoring {path.name}: {error}")
    return None


def _table(data: dict[str, Any], name: str) -> Config:
    exclude: list[str] | None = None
    strict: bool | None = None
    for key in data:
        if key not in KEYS:
            _warn(f"{name}: unknown key {key!r}, expected one of {', '.join(KEYS)}")
    raw_exclude = data.get("exclude")
    if raw_exclude is not None:
        if isinstance(raw_exclude, str):
            exclude = [raw_exclude]
        elif isinstance(raw_exclude, list) and all(isinstance(item, str) for item in raw_exclude):
            exclude = list(raw_exclude)
        else:
            _warn(f"{name}: exclude must be a string or a list of strings, ignoring it")
    raw_strict = data.get("strict")
    if raw_strict is not None:
        if isinstance(raw_strict, bool):
            strict = raw_strict
        else:
            _warn(f"{name}: strict must be true or false, ignoring it")
    return Config(exclude=exclude, strict=strict, source=name)


def _from_pyproject(root: Path) -> Config | None:
    data = _read(root / "pyproject.toml")
    if data is None:
        return None
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return None
    table = tool.get("rulereach")
    if table is None:
        return None
    if not isinstance(table, dict):
        _warn("pyproject.toml: [tool.rulereach] must be a table, ignoring it")
        return None
    return _table(table, "pyproject.toml [tool.rulereach]")


def _from_dedicated_file(root: Path) -> Config | None:
    path = root / ".rulereach.toml"
    data = _read(path)
    if data is None:
        return None
    return _table(data, path.name)


def load(root: Path) -> Config:
    """Return the settings for ``root``, or an empty ``Config`` when there is no file."""

    layers = [layer for layer in (_from_pyproject(root), _from_dedicated_file(root)) if layer]
    merged = Config()
    for layer in layers:
        merged = Config(
            exclude=layer.exclude if layer.exclude is not None else merged.exclude,
            strict=layer.strict if layer.strict is not None else merged.strict,
            source=layer.source,
        )
    return merged
