"""Configuration file loading for rulereach."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib
except ImportError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]


@dataclass
class Config:
    exclude: list[str] = field(default_factory=list)
    strict: bool = False


def _parse_toml_file(path: Path) -> dict[str, Any] | None:
    if tomllib is None or not path.is_file():
        return None
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
            return data if isinstance(data, dict) else None
    except Exception:
        return None


def _apply_config(config: Config, data: dict[str, Any]) -> None:
    if "exclude" in data:
        raw_exclude = data["exclude"]
        if isinstance(raw_exclude, list):
            config.exclude = [str(item) for item in raw_exclude]
        elif isinstance(raw_exclude, str):
            config.exclude = [raw_exclude]

    if "strict" in data:
        raw_strict = data["strict"]
        if isinstance(raw_strict, bool):
            config.strict = raw_strict


def load_config(root: Path) -> Config:
    config = Config()

    # 1. pyproject.toml -> [tool.rulereach]
    pyproject_data = _parse_toml_file(root / "pyproject.toml")
    if pyproject_data and isinstance(pyproject_data.get("tool"), dict):
        tool_data = pyproject_data["tool"]
        if isinstance(tool_data.get("rulereach"), dict):
            _apply_config(config, tool_data["rulereach"])

    # 2. .rulereach.toml -> [tool.rulereach], [rulereach], or top-level
    rulereach_data = _parse_toml_file(root / ".rulereach.toml")
    if rulereach_data:
        if isinstance(rulereach_data.get("tool"), dict) and isinstance(
            rulereach_data["tool"].get("rulereach"), dict
        ):
            _apply_config(config, rulereach_data["tool"]["rulereach"])
        elif isinstance(rulereach_data.get("rulereach"), dict):
            _apply_config(config, rulereach_data["rulereach"])
        else:
            _apply_config(config, rulereach_data)

    return config
