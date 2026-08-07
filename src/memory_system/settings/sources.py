"""Custom Pydantic Settings sources."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic.fields import FieldInfo
from pydantic_settings.sources import PydanticBaseSettingsSource

from memory_system.settings.loader import load_yaml_config


def get_config_dir() -> Path:
    """Return the repository ``configs/`` directory."""
    return Path(__file__).resolve().parents[3] / "configs"


class YamlSettingsSource(PydanticBaseSettingsSource):
    """Inject merged YAML configuration as a settings source."""

    def __init__(
        self,
        settings_cls: type[Any],
        config_dir: Path | None = None,
    ) -> None:
        super().__init__(settings_cls)
        self._config_dir = config_dir or get_config_dir()

    def get_field_value(
        self,
        field: FieldInfo,
        field_name: str,
    ) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        app_env = os.environ.get("APP_ENV", "development")
        return load_yaml_config(self._config_dir, app_env)

    def __repr__(self) -> str:
        return f"YamlSettingsSource(config_dir={self._config_dir!r})"
