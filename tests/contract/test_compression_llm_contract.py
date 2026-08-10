"""Contract tests for compression LLM (STM-007)."""

from __future__ import annotations

import importlib.util
import inspect
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast, get_type_hints

import pytest
from pydantic import BaseModel

from memory_system.domain.models.compression_llm import (
    CompressionFinalizeLlmPayload,
    CompressionLlmFailure,
    CompressionLlmResult,
)
from memory_system.infrastructure.llm import DeepSeekLlmClient, LLMClient
from memory_system.settings import get_settings

_HELPER_PATH = Path(__file__).resolve().parent / "helpers" / "compression_llm_fake.py"
_HELPER_SPEC = importlib.util.spec_from_file_location(
    "compression_llm_fake_helper",
    _HELPER_PATH,
)
assert _HELPER_SPEC is not None and _HELPER_SPEC.loader is not None
_compression_llm_fake = importlib.util.module_from_spec(_HELPER_SPEC)
_HELPER_SPEC.loader.exec_module(_compression_llm_fake)
make_success_response = cast(
    Any,
    _compression_llm_fake.make_success_response,
)

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

EXPECTED_FAILURE_CODES = {
    "llm_empty_output",
    "llm_invalid_output",
    "compression_output_too_large",
    "llm_timeout",
    "llm_request_failed",
    "invalid_compression_input",
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


def test_c1_llm_client_generate_structured_signature() -> None:
    sig = inspect.signature(LLMClient.generate_structured)
    params = list(sig.parameters.keys())
    assert params == [
        "self",
        "model",
        "system_prompt",
        "user_prompt",
        "timeout_seconds",
        "max_output_tokens",
    ]
    hints = get_type_hints(LLMClient.generate_structured)
    assert hints["model"] is str
    assert hints["system_prompt"] is str
    assert hints["user_prompt"] is str
    assert hints["timeout_seconds"] is float
    assert hints["max_output_tokens"] is int
    assert hints["return"] is str


@pytest.mark.asyncio
async def test_c2_deepseek_openai_call_parameter_matrix(
    valid_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import AsyncMock, MagicMock

    settings = get_settings()
    captured: dict[str, Any] = {}

    async def fake_create(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return make_success_response()

    mock_openai = MagicMock()
    mock_openai.chat = MagicMock()
    mock_openai.chat.completions = MagicMock()
    mock_openai.chat.completions.create = AsyncMock(side_effect=fake_create)

    client = DeepSeekLlmClient(settings, openai_client=mock_openai)
    await client.generate_structured(
        model=settings.llm.compression.model,
        system_prompt="system JSON schema",
        user_prompt="user JSON schema",
        timeout_seconds=float(settings.context.compression_llm_timeout_seconds),
        max_output_tokens=settings.llm.compression.max_output_tokens,
    )

    assert captured["response_format"] == {"type": "json_object"}
    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}
    assert captured["temperature"] == 0
    assert captured["stream"] is False
    assert captured["max_tokens"] == settings.llm.compression.max_output_tokens
    assert captured["timeout"] == float(settings.context.compression_llm_timeout_seconds)


def test_c3_compression_llm_failure_error_codes_stable() -> None:
    schema = CompressionLlmFailure.model_json_schema()
    error_code_schema = schema["properties"]["error_code"]
    enum_values = set(error_code_schema["enum"])
    assert enum_values == EXPECTED_FAILURE_CODES


def test_c4_compression_finalize_llm_payload_fields() -> None:
    fields = set(CompressionFinalizeLlmPayload.model_fields.keys())
    assert fields == {"compressed_context", "new_compressed_context_tokens"}
    payload = CompressionFinalizeLlmPayload(
        compressed_context="summary",
        new_compressed_context_tokens=10,
    )
    assert isinstance(payload, BaseModel)
    result_fields = set(CompressionLlmResult.model_fields.keys())
    assert "outcome" in result_fields
    assert "success" in result_fields
    assert "failure" in result_fields
