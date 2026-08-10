"""STM-001 directed unit tests for §1.2.1 / §1.2.6 context inequality chains."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from memory_system.settings import Settings, get_settings

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


def _assert_positive_inequality_chains(settings: Settings) -> None:
    context = settings.context
    memory_extraction = settings.memory_extraction

    assert (
        context.max_message_estimated_tokens
        <= context.max_archive_estimated_tokens
        <= memory_extraction.max_archive_estimated_tokens
    )
    assert (
        context.compression_target_tokens
        < context.compression_trigger_tokens
        < context.max_working_memory_estimated_tokens
    )
    assert context.max_message_estimated_tokens < context.max_working_memory_estimated_tokens
    assert (
        context.max_compressed_context_estimated_tokens < context.compression_trigger_tokens
    )


def test_default_configuration_passes_and_chains_hold(valid_env: None) -> None:
    settings = get_settings()
    _assert_positive_inequality_chains(settings)


def test_mandatory_max_compressed_less_than_trigger_passes(valid_env: None) -> None:
    settings = get_settings()
    assert (
        settings.context.max_compressed_context_estimated_tokens
        < settings.context.compression_trigger_tokens
    )


def test_mandatory_max_compressed_equal_to_trigger_fails(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    trigger = "5000"
    monkeypatch.setenv("CONTEXT__COMPRESSION_TRIGGER_TOKENS", trigger)
    monkeypatch.setenv("CONTEXT__MAX_COMPRESSED_CONTEXT_ESTIMATED_TOKENS", trigger)
    with pytest.raises(ValidationError):
        get_settings()


def test_mandatory_max_compressed_greater_than_trigger_fails(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    monkeypatch.setenv("CONTEXT__COMPRESSION_TRIGGER_TOKENS", "5000")
    monkeypatch.setenv("CONTEXT__MAX_COMPRESSED_CONTEXT_ESTIMATED_TOKENS", "6000")
    with pytest.raises(ValidationError):
        get_settings()


def test_archive_chain_break_fails(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    monkeypatch.setenv("CONTEXT__MAX_MESSAGE_ESTIMATED_TOKENS", "9000")
    with pytest.raises(ValidationError):
        get_settings()


def test_compression_chain_break_fails(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    monkeypatch.setenv("CONTEXT__COMPRESSION_TARGET_TOKENS", "6000")
    monkeypatch.setenv("CONTEXT__COMPRESSION_TRIGGER_TOKENS", "5000")
    with pytest.raises(ValidationError):
        get_settings()


def test_message_working_chain_break_fails(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    monkeypatch.setenv("CONTEXT__MAX_MESSAGE_ESTIMATED_TOKENS", "15000")
    with pytest.raises(ValidationError):
        get_settings()
