"""Opt-in integration tests against real DeepSeek compression LLM API."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator

import pytest

from memory_system.domain.enums.working_memory import MessageRole
from memory_system.domain.models.compression_llm import (
    CompressionLlmInput,
    CompressionLlmOutcome,
)
from memory_system.domain.models.context_archive import ContextArchiveMessage
from memory_system.domain.services.compression_llm_service import run_compression_llm
from memory_system.infrastructure.llm import DeepSeekLlmClient
from memory_system.settings import get_settings

INTEGRATION_ENV_FLAG = "RUN_COMPRESSION_LLM_INTEGRATION"
INTEGRATION_API_KEY_ENV = "LLM__API_KEY"


def _integration_enabled() -> bool:
    flag = os.environ.get(INTEGRATION_ENV_FLAG, "")
    api_key = os.environ.get(INTEGRATION_API_KEY_ENV, "")
    return flag == "1" and bool(api_key.strip())


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_r1_real_deepseek_compression_llm() -> None:
    if not _integration_enabled():
        pytest.skip(
            f"Set {INTEGRATION_ENV_FLAG}=1 and {INTEGRATION_API_KEY_ENV} "
            "to run integration tests"
        )

    settings = get_settings()
    client = DeepSeekLlmClient(settings)
    input_data = CompressionLlmInput(
        existing_compressed_context="",
        archived_messages=[
            ContextArchiveMessage(
                message_id="msg_int_001",
                role=MessageRole.USER,
                content="User asked about memory compression.",
                timestamp=1,
            ),
            ContextArchiveMessage(
                message_id="msg_int_002",
                role=MessageRole.ASSISTANT,
                content="Compression reduces working memory size.",
                timestamp=2,
            ),
        ],
        max_compressed_context_estimated_tokens=settings.context.max_compressed_context_estimated_tokens,
    )

    result = await run_compression_llm(input_data, client, settings)

    assert result.outcome == CompressionLlmOutcome.SUCCESS
    assert result.success is not None
    assert isinstance(result.success.compressed_context, str)
    json.dumps({"compressed_context": result.success.compressed_context})
