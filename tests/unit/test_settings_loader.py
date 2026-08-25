"""Unit tests for settings YAML loading and source priority."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from memory_system.settings import get_settings
from memory_system.settings.loader import ConfigLoadError, load_yaml_config
from memory_system.settings.models import Settings
from memory_system.settings.sources import YamlSettingsSource

VALID_ENV: dict[str, str] = {
    "APP_ENV": "test",
    "REDIS__URI": "redis://redis:6379/0",
    "MONGODB__URI": "mongodb://mongodb:27017/memory_system",
    "KAFKA__BOOTSTRAP_SERVERS": "kafka:9092",
    "NEO4J__URI": "neo4j://neo4j:7687",
    "ELASTICSEARCH__URL": "http://elasticsearch:9200",
    "LLM__BASE_URL": "https://api.deepseek.com",
    "LLM__API_KEY": "sk-example-replace-me",
    "LLM__COMPRESSION__MODEL": "deepseek-v4-flash",
    "LLM__EXTRACTION__MODEL": "deepseek-v4-flash",
    "EMBEDDING__MODEL_ID": "BAAI/bge-m3",
    "EMBEDDING__BASE_URL": "http://embedding-service:80",
    "MEMORY_API_KEY": "dev-memory-api-key-change-me",
    "MEMORY_ADMIN_API_KEY": "dev-memory-admin-key-change-me",
    "EMBEDDING_EFFECTIVE_RUNTIME_MODE": "cpu",
    "EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET": "4096",
    "SILICONFLOW_API_KEY": "sk-example-replace-me",
}


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)


def test_loads_base_yaml_with_app_env_development(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    settings = get_settings()
    assert settings.context.compression_trigger_tokens == 5000
    assert settings.memory_extraction.prompt_version == "memory_extraction_v2"


def test_environment_yaml_overrides_nested_keys(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    settings = get_settings()
    assert settings.context.compression_llm_timeout_seconds == 30


def test_env_overrides_yaml_for_context_tokens(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    monkeypatch.setenv("CONTEXT__COMPRESSION_TRIGGER_TOKENS", "8888")
    settings = get_settings()
    assert settings.context.compression_trigger_tokens == 8888


def test_invalid_yaml_syntax_raises_config_error(tmp_path: Path) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / "base.yaml").write_text("context:\n  bad: [unclosed", encoding="utf-8")
    (config_dir / "development.yaml").write_text("", encoding="utf-8")

    with pytest.raises(ConfigLoadError):
        load_yaml_config(config_dir, "development")


@pytest.mark.parametrize(
    ("root_value", "expected_message"),
    [
        ("- item\n", "mapping/object"),
        ("just-a-scalar\n", "mapping/object"),
    ],
)
def test_yaml_root_must_be_mapping(
    tmp_path: Path,
    root_value: str,
    expected_message: str,
) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / "base.yaml").write_text(root_value, encoding="utf-8")
    (config_dir / "development.yaml").write_text("", encoding="utf-8")

    with pytest.raises(ConfigLoadError, match=expected_message):
        load_yaml_config(config_dir, "development")


def test_empty_base_yaml_allows_defaults_and_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / "base.yaml").write_text("", encoding="utf-8")
    (config_dir / "test.yaml").write_text("", encoding="utf-8")

    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)

    merged = load_yaml_config(config_dir, "test")
    assert merged == {}

    monkeypatch.setattr(
        "memory_system.settings.sources.get_config_dir",
        lambda: config_dir,
    )
    settings = get_settings()
    assert settings.context.compression_trigger_tokens == 5000


def test_recursive_merge_preserves_unoverridden_nested_keys(tmp_path: Path) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    base = {
        "context": {
            "compression_trigger_tokens": 5000,
            "compression_target_tokens": 3000,
        }
    }
    override = {"context": {"compression_target_tokens": 2500}}
    (config_dir / "base.yaml").write_text(yaml.safe_dump(base), encoding="utf-8")
    (config_dir / "development.yaml").write_text(yaml.safe_dump(override), encoding="utf-8")

    merged = load_yaml_config(config_dir, "development")
    assert merged["context"]["compression_trigger_tokens"] == 5000
    assert merged["context"]["compression_target_tokens"] == 2500


def test_yaml_settings_source_repr() -> None:
    source = YamlSettingsSource(Settings)
    assert "YamlSettingsSource" in repr(source)


def test_invalid_yaml_prevents_settings_load(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    valid_env: None,
) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / "base.yaml").write_text("- not-a-mapping\n", encoding="utf-8")
    (config_dir / "test.yaml").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "memory_system.settings.sources.get_config_dir",
        lambda: config_dir,
    )

    with pytest.raises(ConfigLoadError):
        get_settings()
