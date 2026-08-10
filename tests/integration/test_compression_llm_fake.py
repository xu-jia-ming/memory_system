"""Integration tests for compression LLM with FakeLlmClient (STM-007)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from memory_system.domain.enums.working_memory import MessageRole
from memory_system.domain.models.compression_llm import (
    CompressionLlmInput,
    CompressionLlmOutcome,
)
from memory_system.domain.models.context_archive import ContextArchiveMessage
from memory_system.domain.services.compression_llm_service import run_compression_llm
from memory_system.domain.services.token_estimator import estimate_tokens
from memory_system.infrastructure.llm import FakeLlmClient
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
    "SILICONFLOW_API_KEY": "sk-example-replace-me",
}


def _input() -> CompressionLlmInput:
    return CompressionLlmInput(
        existing_compressed_context="prior",
        archived_messages=[
            ContextArchiveMessage(
                message_id="msg_001",
                role=MessageRole.USER,
                content="integration hello",
                timestamp=1,
            )
        ],
        max_compressed_context_estimated_tokens=1000,
    )


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i1_end_to_end_success(valid_env: None) -> None:
    settings = get_settings()
    client = FakeLlmClient(success_content='{"compressed_context":"integration ok"}')
    result = await run_compression_llm(_input(), client, settings)
    assert result.outcome == CompressionLlmOutcome.SUCCESS
    assert result.success is not None
    assert result.success.compressed_context == "integration ok"
    assert result.success.new_compressed_context_tokens == estimate_tokens("integration ok")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i2_fake_timeout(valid_env: None) -> None:
    settings = get_settings()
    client = FakeLlmClient(mode="timeout")
    result = await run_compression_llm(_input(), client, settings)
    assert result.outcome == CompressionLlmOutcome.FAILURE
    assert result.failure is not None
    assert result.failure.error_code == "llm_timeout"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i3_fake_provider_error(valid_env: None) -> None:
    settings = get_settings()
    client = FakeLlmClient(mode="provider_error")
    result = await run_compression_llm(_input(), client, settings)
    assert result.outcome == CompressionLlmOutcome.FAILURE
    assert result.failure is not None
    assert result.failure.error_code == "llm_request_failed"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i4_fake_invalid_json_persistent(valid_env: None) -> None:
    settings = get_settings()
    client = FakeLlmClient(mode="invalid_json")
    result = await run_compression_llm(_input(), client, settings)
    assert result.outcome == CompressionLlmOutcome.FAILURE
    assert result.failure is not None
    assert result.failure.error_code == "llm_invalid_output"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i5_fake_schema_invalid_persistent(valid_env: None) -> None:
    settings = get_settings()
    client = FakeLlmClient(mode="schema_invalid")
    result = await run_compression_llm(_input(), client, settings)
    assert result.outcome == CompressionLlmOutcome.FAILURE
    assert result.failure is not None
    assert result.failure.error_code == "llm_invalid_output"
