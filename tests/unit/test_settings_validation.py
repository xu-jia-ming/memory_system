"""Unit tests for cross-field settings validation."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from memory_system.settings import get_settings

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


def test_default_configuration_is_valid(valid_env: None) -> None:
    settings = get_settings()
    assert settings.shutdown.memory_api_timeout_seconds == 450
    assert settings.context.compression_lock_ttl_seconds == 420


def test_absolute_min_recent_messages_must_not_exceed_preferred(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    monkeypatch.setenv("CONTEXT__ABSOLUTE_MIN_RECENT_MESSAGES", "20")
    monkeypatch.setenv("CONTEXT__PREFERRED_RECENT_MESSAGES", "10")
    with pytest.raises(ValidationError):
        get_settings()


def test_archive_token_chain_validation(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    monkeypatch.setenv("CONTEXT__MAX_ARCHIVE_ESTIMATED_TOKENS", "9000")
    with pytest.raises(ValidationError):
        get_settings()


def test_compression_target_must_be_less_than_trigger(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    monkeypatch.setenv("CONTEXT__COMPRESSION_TARGET_TOKENS", "6000")
    monkeypatch.setenv("CONTEXT__COMPRESSION_TRIGGER_TOKENS", "5000")
    with pytest.raises(ValidationError):
        get_settings()


def test_compression_lock_ttl_formula(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    monkeypatch.setenv("CONTEXT__COMPRESSION_LOCK_TTL_SECONDS", "100")
    with pytest.raises(ValidationError):
        get_settings()


def test_memory_consolidation_weights_must_sum_to_one(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    monkeypatch.setenv("MEMORY_CONSOLIDATION__CONFIDENCE_WEIGHT", "0.40")
    monkeypatch.setenv("MEMORY_CONSOLIDATION__EVIDENCE_WEIGHT", "0.40")
    with pytest.raises(ValidationError):
        get_settings()


def test_memory_retrieval_score_weights_must_sum_to_one(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    monkeypatch.setenv("MEMORY_RETRIEVAL__RETRIEVAL_SCORE_WEIGHT", "0.20")
    with pytest.raises(ValidationError):
        get_settings()


@pytest.mark.parametrize(
    "env_key",
    [
        "MEMORY_RETRIEVAL__RETRIEVAL_SCORE_WEIGHT",
        "MEMORY_RETRIEVAL__IMPORTANCE_WEIGHT",
    ],
)
def test_memory_retrieval_score_weight_bounds(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
    env_key: str,
) -> None:
    monkeypatch.setenv(env_key, "1.5")
    with pytest.raises(ValidationError):
        get_settings()


@pytest.mark.parametrize(
    "env_key",
    [
        "MEMORY_RETRIEVAL__GRAPH_DECAY",
        "MEMORY_RETRIEVAL__CONFLICTED_PENALTY",
        "MEMORY_RETRIEVAL__SUPERSEDED_PENALTY",
    ],
)
def test_memory_retrieval_penalty_bounds(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
    env_key: str,
) -> None:
    monkeypatch.setenv(env_key, "1.5")
    with pytest.raises(ValidationError):
        get_settings()


def test_vector_num_candidates_must_cover_vector_top_n(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    monkeypatch.setenv("MEMORY_RETRIEVAL__VECTOR_TOP_N", "50")
    monkeypatch.setenv("MEMORY_RETRIEVAL__VECTOR_NUM_CANDIDATES", "10")
    with pytest.raises(ValidationError):
        get_settings()


def test_shutdown_memory_api_timeout_must_be_below_compose_grace(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    monkeypatch.setenv("SHUTDOWN__MEMORY_API_TIMEOUT_SECONDS", "480")
    with pytest.raises(ValidationError):
        get_settings()


def test_shutdown_memory_api_timeout_must_exceed_compression_lock_ttl(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    monkeypatch.setenv("SHUTDOWN__MEMORY_API_TIMEOUT_SECONDS", "400")
    with pytest.raises(ValidationError):
        get_settings()


def test_shutdown_extraction_worker_timeout_must_be_below_grace(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    monkeypatch.setenv("SHUTDOWN__EXTRACTION_WORKER_TIMEOUT_SECONDS", "300")
    with pytest.raises(ValidationError):
        get_settings()


def test_shutdown_consolidation_worker_timeout_must_be_below_grace(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    monkeypatch.setenv("SHUTDOWN__CONSOLIDATION_WORKER_TIMEOUT_SECONDS", "300")
    with pytest.raises(ValidationError):
        get_settings()


def test_yaml_override_can_trigger_validation_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    valid_env: None,
) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / "base.yaml").write_text(
        yaml.safe_dump({"context": {"compression_target_tokens": 6000}}),
        encoding="utf-8",
    )
    (config_dir / "test.yaml").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "memory_system.settings.sources.get_config_dir",
        lambda: config_dir,
    )

    with pytest.raises(ValidationError):
        get_settings()
