"""Unit tests for HeuristicTokenCountAdapter (STM-001 estimate_tokens wrapper)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from memory_system.domain.services.token_estimator import estimate_tokens
from memory_system.infrastructure.tokenize.heuristic_token_count_adapter import (
    HeuristicTokenCountAdapter,
)

_U1_TEXTS = (
    "",
    "中文测试",
    "Hello 世界 mixed",
    "abcd",
    "中",
)


@pytest.mark.asyncio
@pytest.mark.parametrize("text", _U1_TEXTS)
async def test_adapter_count_tokens_equals_estimate_tokens(text: str) -> None:
    adapter = HeuristicTokenCountAdapter()
    assert await adapter.count_tokens(text) == estimate_tokens(text)


@pytest.mark.asyncio
async def test_adapter_zero_http_without_client() -> None:
    adapter = HeuristicTokenCountAdapter()
    dummy = AsyncMock()
    assert await adapter.count_tokens("中文") == estimate_tokens("中文")
    dummy.post.assert_not_called()
    dummy.request.assert_not_called()
