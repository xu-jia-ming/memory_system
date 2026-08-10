"""Unit tests for DeepSeek LLM client (STM-007)."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import Request
from openai import APITimeoutError, AsyncOpenAI

from memory_system.infrastructure.llm import DeepSeekLlmClient, LlmServiceError
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


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)


def _make_completion(content: str) -> MagicMock:
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.mark.asyncio
async def test_generate_structured_returns_raw_content(valid_env: None) -> None:
    settings = get_settings()
    mock_openai = MagicMock(spec=AsyncOpenAI)
    mock_openai.chat = MagicMock()
    mock_openai.chat.completions = MagicMock()
    mock_openai.chat.completions.create = AsyncMock(
        return_value=_make_completion('{"compressed_context":"ok"}'),
    )
    client = DeepSeekLlmClient(settings, openai_client=mock_openai)

    result = await client.generate_structured(
        model="deepseek-v4-flash",
        system_prompt="system",
        user_prompt="user",
        timeout_seconds=30.0,
        max_output_tokens=2048,
    )

    assert result == '{"compressed_context":"ok"}'
    mock_openai.chat.completions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_structured_passes_openai_parameters(valid_env: None) -> None:
    settings = get_settings()
    mock_openai = MagicMock(spec=AsyncOpenAI)
    mock_openai.chat = MagicMock()
    mock_openai.chat.completions = MagicMock()
    mock_openai.chat.completions.create = AsyncMock(
        return_value=_make_completion('{"compressed_context":""}'),
    )
    client = DeepSeekLlmClient(settings, openai_client=mock_openai)

    await client.generate_structured(
        model="deepseek-v4-flash",
        system_prompt="system-json",
        user_prompt="user-json",
        timeout_seconds=120.0,
        max_output_tokens=2048,
    )

    kwargs = mock_openai.chat.completions.create.await_args.kwargs
    assert kwargs["model"] == "deepseek-v4-flash"
    assert kwargs["stream"] is False
    assert kwargs["temperature"] == 0
    assert kwargs["max_tokens"] == 2048
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["extra_body"] == {"thinking": {"type": "disabled"}}
    assert kwargs["timeout"] == 120.0
    assert kwargs["messages"] == [
        {"role": "system", "content": "system-json"},
        {"role": "user", "content": "user-json"},
    ]


@pytest.mark.asyncio
async def test_timeout_maps_to_llm_timeout_no_retry(valid_env: None) -> None:
    settings = get_settings()
    mock_openai = MagicMock(spec=AsyncOpenAI)
    mock_openai.chat = MagicMock()
    mock_openai.chat.completions = MagicMock()
    mock_openai.chat.completions.create = AsyncMock(
        side_effect=APITimeoutError(Request("POST", "https://api.deepseek.com")),
    )
    client = DeepSeekLlmClient(settings, openai_client=mock_openai)

    with pytest.raises(LlmServiceError) as exc_info:
        await client.generate_structured(
            model="deepseek-v4-flash",
            system_prompt="system",
            user_prompt="user",
            timeout_seconds=1.0,
            max_output_tokens=2048,
        )

    assert exc_info.value.code == "llm_timeout"
    assert mock_openai.chat.completions.create.await_count == 1


@pytest.mark.asyncio
async def test_api_status_error_maps_to_request_failed(valid_env: None) -> None:
    settings = get_settings()
    mock_openai = MagicMock(spec=AsyncOpenAI)
    mock_openai.chat = MagicMock()
    mock_openai.chat.completions = MagicMock()

    from openai import APIStatusError

    api_error = APIStatusError(
        message="service unavailable",
        response=MagicMock(status_code=503),
        body=None,
    )
    mock_openai.chat.completions.create = AsyncMock(side_effect=api_error)
    client = DeepSeekLlmClient(settings, openai_client=mock_openai)

    with pytest.raises(LlmServiceError) as exc_info:
        await client.generate_structured(
            model="deepseek-v4-flash",
            system_prompt="system",
            user_prompt="user",
            timeout_seconds=30.0,
            max_output_tokens=2048,
        )

    assert exc_info.value.code == "llm_request_failed"
    assert exc_info.value.status_code == 503
    assert mock_openai.chat.completions.create.await_count == 1


@pytest.mark.asyncio
async def test_generate_structured_null_content_returns_empty_string(
    valid_env: None,
) -> None:
    settings = get_settings()
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

    result = await client.generate_structured(
        model="deepseek-v4-flash",
        system_prompt="system",
        user_prompt="user",
        timeout_seconds=30.0,
        max_output_tokens=2048,
    )

    assert result == ""
    mock_openai.chat.completions.create.assert_awaited_once()


def test_error_string_redacts_api_key(valid_env: None) -> None:
    error = LlmServiceError(
        code="llm_request_failed",
        sanitized_message="Bearer sk-secret-key-123 failed",
        status_code=401,
    )
    rendered = str(error)
    assert "sk-secret-key-123" not in rendered
    assert "Bearer" not in rendered
