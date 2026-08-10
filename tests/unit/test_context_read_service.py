"""Unit tests for context read domain service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from memory_system.domain.enums.context_read import ContextReadStatus
from memory_system.domain.enums.working_memory import MessageRole
from memory_system.domain.models.context_read import ContextReadInput
from memory_system.domain.models.working_memory import WorkingMemoryMessage
from memory_system.domain.services.context_read_service import (
    ContextReadFailure,
    read_working_memory_context,
)
from memory_system.infrastructure.redis.working_memory_message_codec import message_to_json

USER_ID = "user_001"
SESSION_ID = "session_001"
FIXED_NOW = 1_700_000_000


def _input(
    user_id: str = USER_ID,
    session_id: str = SESSION_ID,
) -> ContextReadInput:
    return ContextReadInput(user_id=user_id, session_id=session_id)


def _message_json(
    message_id: str = "msg-1",
    content: str = "hello",
) -> str:
    return message_to_json(
        WorkingMemoryMessage(
            message_id=message_id,
            role=MessageRole.USER,
            content=content,
            estimated_tokens=1,
            timestamp=FIXED_NOW,
        )
    )


@pytest.mark.asyncio
async def test_success_snapshot_assembly() -> None:
    message_json = _message_json()
    mock_redis = MagicMock()

    with patch(
        "memory_system.domain.services.context_read_service.execute_context_read_lua",
        new_callable=AsyncMock,
        return_value=("1", "summary text", [message_json]),
    ):
        result = await read_working_memory_context(redis=mock_redis, input=_input())

    assert result.status == ContextReadStatus.SUCCESS
    assert result.snapshot is not None
    assert result.snapshot.compression_version == 1
    assert result.snapshot.compressed_context == "summary text"
    assert len(result.snapshot.messages) == 1
    assert result.snapshot.messages[0].message_id == "msg-1"
    assert result.snapshot.messages[0].content == "hello"


@pytest.mark.asyncio
async def test_empty_compressed_context_string_not_none() -> None:
    mock_redis = MagicMock()

    with patch(
        "memory_system.domain.services.context_read_service.execute_context_read_lua",
        new_callable=AsyncMock,
        return_value=("0", "", []),
    ):
        result = await read_working_memory_context(redis=mock_redis, input=_input())

    assert result.status == ContextReadStatus.SUCCESS
    assert result.snapshot is not None
    assert result.snapshot.compressed_context == ""
    assert result.snapshot.messages == []


@pytest.mark.asyncio
async def test_session_not_found_no_snapshot() -> None:
    mock_redis = MagicMock()

    with patch(
        "memory_system.domain.services.context_read_service.execute_context_read_lua",
        new_callable=AsyncMock,
        return_value=ContextReadStatus.SESSION_NOT_FOUND,
    ):
        result = await read_working_memory_context(redis=mock_redis, input=_input())

    assert result.status == ContextReadStatus.SESSION_NOT_FOUND
    assert result.snapshot is None


@pytest.mark.asyncio
async def test_invalid_session_state_no_snapshot() -> None:
    mock_redis = MagicMock()

    with patch(
        "memory_system.domain.services.context_read_service.execute_context_read_lua",
        new_callable=AsyncMock,
        return_value=ContextReadStatus.INVALID_SESSION_STATE,
    ):
        result = await read_working_memory_context(redis=mock_redis, input=_input())

    assert result.status == ContextReadStatus.INVALID_SESSION_STATE
    assert result.snapshot is None


@pytest.mark.asyncio
async def test_malformed_message_json_raises_context_read_failure() -> None:
    mock_redis = MagicMock()

    with patch(
        "memory_system.domain.services.context_read_service.execute_context_read_lua",
        new_callable=AsyncMock,
        return_value=("0", "", ["not-valid-json"]),
    ):
        with pytest.raises(ContextReadFailure):
            await read_working_memory_context(redis=mock_redis, input=_input())


@pytest.mark.asyncio
async def test_empty_messages_list_success() -> None:
    mock_redis = MagicMock()

    with patch(
        "memory_system.domain.services.context_read_service.execute_context_read_lua",
        new_callable=AsyncMock,
        return_value=("0", "", []),
    ):
        result = await read_working_memory_context(redis=mock_redis, input=_input())

    assert result.status == ContextReadStatus.SUCCESS
    assert result.snapshot is not None
    assert result.snapshot.messages == []
