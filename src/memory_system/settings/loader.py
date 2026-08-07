"""YAML configuration loader with recursive merge."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

_CONFIG_ROOT_ERROR = "YAML configuration root must be a mapping/object"


class ConfigLoadError(ValueError):
    """Raised when YAML configuration cannot be loaded or merged."""


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    content = path.read_text(encoding="utf-8")
    if not content.strip():
        return {}
    loaded = yaml.safe_load(content)
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ConfigLoadError(f"{path}: {_CONFIG_ROOT_ERROR}")
    return loaded


def load_yaml_config(config_dir: Path, app_env: str) -> dict[str, Any]:
    """Load and merge ``base.yaml`` with ``{app_env}.yaml`` using recursive dict merge."""
    base_path = config_dir / "base.yaml"
    env_path = config_dir / f"{app_env}.yaml"

    try:
        base_config = _load_yaml_file(base_path)
        env_config = _load_yaml_file(env_path)
    except yaml.YAMLError as exc:
        raise ConfigLoadError(f"Failed to parse YAML configuration: {exc}") from exc

    return _deep_merge(base_config, env_config)
