"""Unit tests for message write domain service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from memory_system.domain.enums.message_write import MessageWriteStatus
from memory_system.domain.enums.working_memory import MessageRole
from memory_system.domain.models.message_write import MessageWriteInput
from memory_system.domain.services.message_write_service import (
    MessageWriteIdMismatchError,
    MessageWriteValidationError,
    write_message,
)
from memory_system.domain.services.token_estimator import estimate_tokens
from memory_system.infrastructure.redis.keys import (
    working_memory_message_ids_key,
    working_memory_messages_key,
    working_memory_meta_key,
)
from memory_system.settings.models import ContextSettings

USER_ID = "user_001"
SESSION_ID = "session_001"
MESSAGE_ID = "123e4567-e89b-42d3-a456-426614174000"
FIXED_NOW = 1_700_000_000


def _ascii_content_for_tokens(token_count: int) -> str:
    return "a" * (4 * token_count)


def _context(
    max_message: int = 2000,
    max_wm: int = 12000,
) -> ContextSettings:
    return ContextSettings(
        max_message_estimated_tokens=max_message,
        max_working_memory_estimated_tokens=max_wm,
    )


def _input(
    user_id: str = USER_ID,
    session_id: str = SESSION_ID,
    message_id: str = MESSAGE_ID,
    role: MessageRole = MessageRole.USER,
    content: str = "hello",
    timestamp: int | None = None,
) -> MessageWriteInput:
    return MessageWriteInput(
        user_id=user_id,
        session_id=session_id,
        message_id=message_id,
        role=role,
        content=content,
        timestamp=timestamp,
    )


@pytest.mark.asyncio
async def test_write_message_uses_estimate_tokens() -> None:
    content = "Hello 世界"
    expected_tokens = estimate_tokens(content)
    mock_redis = MagicMock()
    mock_redis.hget = AsyncMock(return_value=str(expected_tokens))

    with patch(
        "memory_system.domain.services.message_write_service.execute_message_write_lua",
        new_callable=AsyncMock,
        return_value=MessageWriteStatus.SUCCESS,
    ) as mock_lua:
        result = await write_message(
            redis=mock_redis,
            input=_input(content=content),
            context=_context(),
            clock=lambda: FIXED_NOW,
        )

    mock_lua.assert_awaited_once()
    call_kwargs = mock_lua.await_args
    assert call_kwargs is not None
    assert call_kwargs.kwargs["message_estimated_tokens"] == expected_tokens
    assert result.status == MessageWriteStatus.SUCCESS
    assert result.message_estimated_tokens == expected_tokens


@pytest.mark.asyncio
async def test_message_too_large_skips_lua() -> None:
    max_message = 10
    content = _ascii_content_for_tokens(max_message + 1)
    mock_redis = MagicMock()

    with patch(
        "memory_system.domain.services.message_write_service.execute_message_write_lua",
        new_callable=AsyncMock,
    ) as mock_lua:
        result = await write_message(
            redis=mock_redis,
            input=_input(content=content),
            context=_context(max_message=max_message),
            clock=lambda: FIXED_NOW,
        )

    mock_lua.assert_not_awaited()
    assert result.status == MessageWriteStatus.MESSAGE_TOO_LARGE


@pytest.mark.asyncio
async def test_message_exact_max_message_boundary_allowed() -> None:
    max_message = 10
    content = _ascii_content_for_tokens(max_message)
    mock_redis = MagicMock()
    mock_redis.hget = AsyncMock(return_value=str(max_message))

    with patch(
        "memory_system.domain.services.message_write_service.execute_message_write_lua",
        new_callable=AsyncMock,
        return_value=MessageWriteStatus.SUCCESS,
    ) as mock_lua:
        result = await write_message(
            redis=mock_redis,
            input=_input(content=content),
            context=_context(max_message=max_message),
            clock=lambda: FIXED_NOW,
        )

    mock_lua.assert_awaited_once()
    assert result.status == MessageWriteStatus.SUCCESS


@pytest.mark.asyncio
async def test_empty_content_rejected_before_lua() -> None:
    mock_redis = MagicMock()
    with patch(
        "memory_system.domain.services.message_write_service.execute_message_write_lua",
        new_callable=AsyncMock,
    ) as mock_lua:
        with pytest.raises(MessageWriteValidationError, match="content must not be empty"):
            await write_message(
                redis=mock_redis,
                input=_input(content="   "),
                context=_context(),
                clock=lambda: FIXED_NOW,
            )
    mock_lua.assert_not_awaited()


@pytest.mark.asyncio
async def test_lua_success_passes_keys_and_argv() -> None:
    mock_redis = MagicMock()
    mock_redis.hget = AsyncMock(return_value="2")

    with patch(
        "memory_system.domain.services.message_write_service.execute_message_write_lua",
        new_callable=AsyncMock,
        return_value=MessageWriteStatus.SUCCESS,
    ) as mock_lua:
        await write_message(
            redis=mock_redis,
            input=_input(content="hello"),
            context=_context(),
            clock=lambda: FIXED_NOW,
        )

    kwargs = mock_lua.await_args
    assert kwargs is not None
    assert kwargs.kwargs["user_id"] == USER_ID
    assert kwargs.kwargs["session_id"] == SESSION_ID
    assert kwargs.kwargs["message_id"] == MESSAGE_ID
    assert kwargs.kwargs["updated_time"] == FIXED_NOW
    assert '"message_id":"123e4567-e89b-42d3-a456-426614174000"' in kwargs.kwargs["message_json"]


@pytest.mark.asyncio
async def test_lua_duplicate_maps_to_result() -> None:
    mock_redis = MagicMock()
    with patch(
        "memory_system.domain.services.message_write_service.execute_message_write_lua",
        new_callable=AsyncMock,
        return_value=MessageWriteStatus.DUPLICATE,
    ):
        result = await write_message(
            redis=mock_redis,
            input=_input(),
            context=_context(),
            clock=lambda: FIXED_NOW,
        )
    assert result.status == MessageWriteStatus.DUPLICATE


@pytest.mark.asyncio
async def test_serialized_message_id_mismatch_fails_closed() -> None:
    mock_redis = MagicMock()
    with patch(
        "memory_system.domain.services.message_write_service.message_to_json",
        return_value='{"message_id":"other-id","role":"user","content":"x","estimated_tokens":1,"timestamp":1}',
    ):
        with patch(
            "memory_system.domain.services.message_write_service.execute_message_write_lua",
            new_callable=AsyncMock,
        ) as mock_lua:
            with pytest.raises(MessageWriteIdMismatchError):
                await write_message(
                    redis=mock_redis,
                    input=_input(),
                    context=_context(),
                    clock=lambda: FIXED_NOW,
                )
            mock_lua.assert_not_awaited()


@pytest.mark.asyncio
async def test_redis_failure_propagates() -> None:
    mock_redis = MagicMock()
    with patch(
        "memory_system.domain.services.message_write_service.execute_message_write_lua",
        new_callable=AsyncMock,
        side_effect=ConnectionError("redis down"),
    ):
        with pytest.raises(ConnectionError, match="redis down"):
            await write_message(
                redis=mock_redis,
                input=_input(),
                context=_context(),
                clock=lambda: FIXED_NOW,
            )


def test_key_helpers_used_for_write_paths() -> None:
    assert working_memory_meta_key(USER_ID, SESSION_ID) == "memory:working:user_001:session_001"
    assert working_memory_messages_key(USER_ID, SESSION_ID) == (
        "memory:working:user_001:session_001:messages"
    )
    assert working_memory_message_ids_key(USER_ID, SESSION_ID) == (
        "memory:working:user_001:session_001:message_ids"
    )
