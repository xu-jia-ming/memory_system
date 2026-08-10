"""Unit tests for compression lock acquire/release."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from memory_system.infrastructure.redis.compression_lock_repository import (
    acquire_compression_lock,
    release_compression_lock,
)
from memory_system.infrastructure.redis.keys import compression_lock_key

USER_ID = "user_001"
SESSION_ID = "session_001"
TOKEN = "token-aaaa-bbbb"
TTL = 420


@pytest.mark.asyncio
async def test_acquire_success_uses_set_nx_ex() -> None:
    mock_redis = MagicMock()
    mock_redis.set = AsyncMock(return_value=True)

    token = await acquire_compression_lock(
        mock_redis,
        user_id=USER_ID,
        session_id=SESSION_ID,
        ttl_seconds=TTL,
        token_factory=lambda: TOKEN,
    )

    assert token == TOKEN
    mock_redis.set.assert_awaited_once_with(
        compression_lock_key(USER_ID, SESSION_ID),
        TOKEN,
        nx=True,
        ex=TTL,
    )


@pytest.mark.asyncio
async def test_acquire_contention_returns_none() -> None:
    mock_redis = MagicMock()
    mock_redis.set = AsyncMock(return_value=None)

    token = await acquire_compression_lock(
        mock_redis,
        user_id=USER_ID,
        session_id=SESSION_ID,
        ttl_seconds=TTL,
        token_factory=lambda: TOKEN,
    )

    assert token is None


@pytest.mark.asyncio
async def test_release_token_match_deletes() -> None:
    mock_redis = MagicMock()
    script = AsyncMock(return_value=1)
    mock_redis.register_script = MagicMock(return_value=script)

    released = await release_compression_lock(
        mock_redis,
        user_id=USER_ID,
        session_id=SESSION_ID,
        token=TOKEN,
    )

    assert released is True
    script.assert_awaited_once()
    call_kwargs = script.await_args
    assert call_kwargs is not None
    assert call_kwargs.kwargs["keys"] == [compression_lock_key(USER_ID, SESSION_ID)]
    assert call_kwargs.kwargs["args"] == [TOKEN]


@pytest.mark.asyncio
async def test_release_token_mismatch_does_not_delete() -> None:
    mock_redis = MagicMock()
    script = AsyncMock(return_value=0)
    mock_redis.register_script = MagicMock(return_value=script)

    released = await release_compression_lock(
        mock_redis,
        user_id=USER_ID,
        session_id=SESSION_ID,
        token="wrong-token",
    )

    assert released is False
