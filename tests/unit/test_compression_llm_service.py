"""Unit tests for compression LLM service (STM-007)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import AsyncOpenAI

from memory_system.domain.enums.working_memory import MessageRole
from memory_system.domain.models.compression_llm import (
    CompressionLlmInput,
    CompressionLlmOutcome,
)
from memory_system.domain.models.context_archive import ContextArchiveMessage
from memory_system.domain.services.compression_llm_service import run_compression_llm
from memory_system.domain.services.token_estimator import estimate_tokens
from memory_system.infrastructure.llm import DeepSeekLlmClient, FakeLlmClient
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

MAX_TOKENS = 1000


def _message() -> ContextArchiveMessage:
    return ContextArchiveMessage(
        message_id="msg_001",
        role=MessageRole.USER,
        content="hello",
        timestamp=1_700_000_000,
    )


def _input(**overrides: object) -> CompressionLlmInput:
    base = {
        "existing_compressed_context": "",
        "archived_messages": [_message()],
        "max_compressed_context_estimated_tokens": MAX_TOKENS,
    }
    base.update(overrides)
    return CompressionLlmInput.model_validate(base)


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def settings(valid_env: None) -> Settings:
    return get_settings()


@pytest.mark.asyncio
async def test_u1_success_non_empty_compressed_context(settings: Settings) -> None:
    client = FakeLlmClient(
        success_content=json.dumps({"compressed_context": "user likes tea"}),
    )
    result = await run_compression_llm(_input(), client, settings)
    assert result.outcome == CompressionLlmOutcome.SUCCESS
    assert result.success is not None
    assert result.success.compressed_context == "user likes tea"
    assert result.success.new_compressed_context_tokens == estimate_tokens("user likes tea")
    assert result.success.prompt_version == "compression_v1"


@pytest.mark.asyncio
async def test_u2_success_empty_compressed_context(settings: Settings) -> None:
    client = FakeLlmClient(success_content='{"compressed_context":""}')
    result = await run_compression_llm(_input(), client, settings)
    assert result.outcome == CompressionLlmOutcome.SUCCESS
    assert result.success is not None
    assert result.success.compressed_context == ""
    assert result.success.new_compressed_context_tokens == 0


@pytest.mark.asyncio
async def test_u3_success_at_token_boundary(settings: Settings) -> None:
    text = "x" * 4000
    assert estimate_tokens(text) == MAX_TOKENS
    client = FakeLlmClient(success_content=json.dumps({"compressed_context": text}))
    result = await run_compression_llm(_input(), client, settings)
    assert result.outcome == CompressionLlmOutcome.SUCCESS
    assert result.success is not None
    assert result.success.new_compressed_context_tokens == MAX_TOKENS


@pytest.mark.asyncio
async def test_u4_failure_output_too_large_no_second_call(settings: Settings) -> None:
    text = "x" * 4001
    assert estimate_tokens(text) > MAX_TOKENS
    client = FakeLlmClient(success_content=json.dumps({"compressed_context": text}))
    result = await run_compression_llm(_input(), client, settings)
    assert result.outcome == CompressionLlmOutcome.FAILURE
    assert result.failure is not None
    assert result.failure.error_code == "compression_output_too_large"
    assert client.call_count == 1


@pytest.mark.asyncio
async def test_u5_failure_null_content_string(settings: Settings) -> None:
    client = FakeLlmClient(mode="empty_content")
    result = await run_compression_llm(_input(), client, settings)
    assert result.outcome == CompressionLlmOutcome.FAILURE
    assert result.failure is not None
    assert result.failure.error_code == "llm_empty_output"
    assert result.failure.attempt_count == 1


@pytest.mark.asyncio
async def test_u5b_deepseek_null_content_maps_to_llm_empty_output(
    settings: Settings,
) -> None:
    mock_openai = MagicMock(spec=AsyncOpenAI)
    mock_openai.chat = MagicMock()
    mock_openai.chat.completions = MagicMock()
    message = MagicMock()
    message.content = None
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    mock_openai.chat.completions.create = AsyncMock(return_value=response)
    client = DeepSeekLlmClient(settings, openai_client=mock_openai)

    result = await run_compression_llm(_input(), client, settings)

    assert result.outcome == CompressionLlmOutcome.FAILURE
    assert result.failure is not None
    assert result.failure.error_code == "llm_empty_output"
    assert result.failure.attempt_count == 1
    mock_openai.chat.completions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_u6_failure_whitespace_content(settings: Settings) -> None:
    client = FakeLlmClient(mode="whitespace_content")
    result = await run_compression_llm(_input(), client, settings)
    assert result.outcome == CompressionLlmOutcome.FAILURE
    assert result.failure is not None
    assert result.failure.error_code == "llm_empty_output"
    assert result.failure.attempt_count == 1


@pytest.mark.asyncio
async def test_u7_failure_invalid_json_twice(settings: Settings) -> None:
    client = FakeLlmClient(mode="invalid_json")
    result = await run_compression_llm(_input(), client, settings)
    assert result.outcome == CompressionLlmOutcome.FAILURE
    assert result.failure is not None
    assert result.failure.error_code == "llm_invalid_output"
    assert result.failure.attempt_count == 2
    assert client.call_count == 2


@pytest.mark.asyncio
async def test_u8_failure_missing_compressed_context_twice(settings: Settings) -> None:
    client = FakeLlmClient(mode="schema_invalid")
    result = await run_compression_llm(_input(), client, settings)
    assert result.outcome == CompressionLlmOutcome.FAILURE
    assert result.failure is not None
    assert result.failure.error_code == "llm_invalid_output"
    assert client.call_count == 2


@pytest.mark.asyncio
async def test_u9_failure_null_compressed_context_twice(settings: Settings) -> None:
    client = FakeLlmClient(success_content='{"compressed_context":null}')
    result = await run_compression_llm(_input(), client, settings)
    assert result.outcome == CompressionLlmOutcome.FAILURE
    assert result.failure is not None
    assert result.failure.error_code == "llm_invalid_output"
    assert client.call_count == 2


@pytest.mark.asyncio
async def test_u10_failure_extra_field_twice(settings: Settings) -> None:
    client = FakeLlmClient(
        success_content='{"compressed_context":"ok","extra":"field"}',
    )
    result = await run_compression_llm(_input(), client, settings)
    assert result.outcome == CompressionLlmOutcome.FAILURE
    assert result.failure is not None
    assert result.failure.error_code == "llm_invalid_output"
    assert client.call_count == 2


@pytest.mark.asyncio
async def test_u11_schema_retry_then_success(settings: Settings) -> None:
    client = FakeLlmClient(
        responses=[
            "not-json",
            json.dumps({"compressed_context": "recovered"}),
        ],
    )
    result = await run_compression_llm(_input(), client, settings)
    assert result.outcome == CompressionLlmOutcome.SUCCESS
    assert result.success is not None
    assert result.success.compressed_context == "recovered"
    assert client.call_count == 2


@pytest.mark.asyncio
async def test_u12_timeout_single_call(settings: Settings) -> None:
    client = FakeLlmClient(mode="timeout")
    result = await run_compression_llm(_input(), client, settings)
    assert result.outcome == CompressionLlmOutcome.FAILURE
    assert result.failure is not None
    assert result.failure.error_code == "llm_timeout"
    assert client.call_count == 1


@pytest.mark.asyncio
async def test_u13_empty_archived_messages_no_llm_call(settings: Settings) -> None:
    client = FakeLlmClient()
    result = await run_compression_llm(
        _input(archived_messages=[]),
        client,
        settings,
    )
    assert result.outcome == CompressionLlmOutcome.FAILURE
    assert result.failure is not None
    assert result.failure.error_code == "invalid_compression_input"
    assert client.call_count == 0
