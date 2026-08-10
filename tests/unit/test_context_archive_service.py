"""Unit tests for context archive domain service."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymongo.errors import DuplicateKeyError

from memory_system.domain.enums.context_archive import ContextArchiveOutcome
from memory_system.domain.enums.working_memory import MessageRole
from memory_system.domain.models.context_archive import (
    ContextArchive,
    ContextArchiveCreateInput,
    ContextArchiveMessage,
)
from memory_system.domain.models.working_memory import WorkingMemoryMessage
from memory_system.domain.services.context_archive_service import (
    ContextArchiveValidationError,
    build_archive_batch_key,
    create_or_reuse_context_archive,
)

USER_ID = "user_001"
SESSION_ID = "session_001"
FIXED_NOW = 1_700_000_000
ARCHIVE_ID = "00000000-0000-4000-8000-000000000099"
EXISTING_ARCHIVE_ID = "11111111-1111-4111-8111-111111111111"


def _message(message_id: str = "msg_001") -> WorkingMemoryMessage:
    return WorkingMemoryMessage(
        message_id=message_id,
        role=MessageRole.USER,
        content="hello",
        estimated_tokens=5,
        timestamp=FIXED_NOW,
    )


def _input(
    *,
    user_id: str = USER_ID,
    session_id: str = SESSION_ID,
    archive_batch_key: str | None = None,
    messages: list[WorkingMemoryMessage] | None = None,
) -> ContextArchiveCreateInput:
    msgs = messages if messages is not None else [_message()]
    key = archive_batch_key or build_archive_batch_key(
        session_id,
        msgs[0].message_id,
        msgs[-1].message_id,
    )
    return ContextArchiveCreateInput(
        user_id=user_id,
        session_id=session_id,
        archive_batch_key=key,
        base_compression_version=0,
        messages=msgs,
    )


def _existing_archive(batch_key: str) -> ContextArchive:
    return ContextArchive(
        archive_id=EXISTING_ARCHIVE_ID,
        user_id=USER_ID,
        session_id=SESSION_ID,
        archive_batch_key=batch_key,
        base_compression_version=0,
        messages=[
            ContextArchiveMessage(
                message_id="msg_001",
                role=MessageRole.USER,
                content="hello",
                timestamp=FIXED_NOW,
            )
        ],
        created_time=FIXED_NOW - 100,
    )


@pytest.mark.asyncio
async def test_create_success_path() -> None:
    mock_mongo = MagicMock()
    input_data = _input()

    with (
        patch(
            "memory_system.domain.services.context_archive_service.insert_context_archive",
            new_callable=AsyncMock,
        ) as mock_insert,
        patch(
            "memory_system.domain.services.context_archive_service.uuid.uuid4",
            return_value=uuid.UUID(ARCHIVE_ID),
        ),
    ):
        result = await create_or_reuse_context_archive(
            mongodb=mock_mongo,
            input=input_data,
            clock=lambda: FIXED_NOW,
        )

    mock_insert.assert_awaited_once()
    assert result.outcome == ContextArchiveOutcome.CREATED
    assert result.archive_id == ARCHIVE_ID
    assert result.archive.archive_id == ARCHIVE_ID
    assert result.archive.created_time == FIXED_NOW


@pytest.mark.asyncio
async def test_reuse_on_batch_key_duplicate() -> None:
    mock_mongo = MagicMock()
    input_data = _input()
    existing = _existing_archive(input_data.archive_batch_key)
    dup_exc = DuplicateKeyError(
        "duplicate key",
        11000,
        {"keyPattern": {"archive_batch_key": 1}, "errmsg": "archive_batch_key_unique"},
    )

    with (
        patch(
            "memory_system.domain.services.context_archive_service.insert_context_archive",
            new_callable=AsyncMock,
            side_effect=dup_exc,
        ) as mock_insert,
        patch(
            "memory_system.domain.services.context_archive_service.find_context_archive_by_batch_key",
            new_callable=AsyncMock,
            return_value=existing,
        ) as mock_find,
    ):
        result = await create_or_reuse_context_archive(
            mongodb=mock_mongo,
            input=input_data,
            clock=lambda: FIXED_NOW,
        )

    mock_insert.assert_awaited_once()
    mock_find.assert_awaited_once_with(mock_mongo, input_data.archive_batch_key)
    assert result.outcome == ContextArchiveOutcome.REUSED
    assert result.archive_id == EXISTING_ARCHIVE_ID
    assert result.archive.archive_id == EXISTING_ARCHIVE_ID


@pytest.mark.asyncio
async def test_non_batch_key_duplicate_propagates() -> None:
    mock_mongo = MagicMock()
    input_data = _input()
    dup_exc = DuplicateKeyError(
        "duplicate key",
        11000,
        {"keyPattern": {"archive_id": 1}, "errmsg": "archive_id_unique"},
    )

    with patch(
        "memory_system.domain.services.context_archive_service.insert_context_archive",
        new_callable=AsyncMock,
        side_effect=dup_exc,
    ):
        with pytest.raises(DuplicateKeyError):
            await create_or_reuse_context_archive(
                mongodb=mock_mongo,
                input=input_data,
                clock=lambda: FIXED_NOW,
            )


@pytest.mark.parametrize(
    ("user_id", "session_id", "messages", "batch_key"),
    [
        ("", SESSION_ID, [_message()], None),
        (USER_ID, "", [_message()], None),
        (USER_ID, SESSION_ID, [], None),
        (USER_ID, SESSION_ID, [_message()], "wrong:key"),
    ],
)
@pytest.mark.asyncio
async def test_validation_fail_closed(
    user_id: str,
    session_id: str,
    messages: list[WorkingMemoryMessage],
    batch_key: str | None,
) -> None:
    mock_mongo = MagicMock()
    if messages:
        key = batch_key or build_archive_batch_key(
            session_id or SESSION_ID,
            messages[0].message_id,
            messages[-1].message_id,
        )
    else:
        key = batch_key or "session_001:msg_001:msg_001"
    input_data = ContextArchiveCreateInput(
        user_id=user_id,
        session_id=session_id,
        archive_batch_key=key,
        base_compression_version=0,
        messages=messages,
    )

    with patch(
        "memory_system.domain.services.context_archive_service.insert_context_archive",
        new_callable=AsyncMock,
    ) as mock_insert:
        with pytest.raises(ContextArchiveValidationError):
            await create_or_reuse_context_archive(
                mongodb=mock_mongo,
                input=input_data,
                clock=lambda: FIXED_NOW,
            )
    mock_insert.assert_not_called()


@pytest.mark.asyncio
async def test_batch_key_mismatch_fail_closed() -> None:
    mock_mongo = MagicMock()
    input_data = _input(archive_batch_key="session_001:wrong:first")

    with patch(
        "memory_system.domain.services.context_archive_service.insert_context_archive",
        new_callable=AsyncMock,
    ) as mock_insert:
        with pytest.raises(ContextArchiveValidationError, match="does not match"):
            await create_or_reuse_context_archive(
                mongodb=mock_mongo,
                input=input_data,
                clock=lambda: FIXED_NOW,
            )
    mock_insert.assert_not_called()
