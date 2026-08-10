"""Unit tests for Context Archive domain models."""

from __future__ import annotations

import pytest

from memory_system.domain.enums.working_memory import MessageRole
from memory_system.domain.models.context_archive import (
    archive_document_from_input,
    wm_message_to_archive_message,
)
from memory_system.domain.models.working_memory import WorkingMemoryMessage

USER_ID = "user_001"
SESSION_ID = "session_001"
FIXED_NOW = 1_700_000_000


def _wm_message(
    message_id: str = "msg_001",
    content: str = "hello",
    estimated_tokens: int = 42,
) -> WorkingMemoryMessage:
    return WorkingMemoryMessage(
        message_id=message_id,
        role=MessageRole.USER,
        content=content,
        estimated_tokens=estimated_tokens,
        timestamp=FIXED_NOW,
    )


def test_wm_message_to_archive_message_strips_estimated_tokens() -> None:
    archive_msg = wm_message_to_archive_message(_wm_message(estimated_tokens=99))
    dumped = archive_msg.model_dump()
    assert set(dumped.keys()) == {"message_id", "role", "content", "timestamp"}
    assert "estimated_tokens" not in dumped
    assert archive_msg.message_id == "msg_001"
    assert archive_msg.role == MessageRole.USER
    assert archive_msg.content == "hello"
    assert archive_msg.timestamp == FIXED_NOW


def test_archive_document_from_input_messages_have_four_fields_only() -> None:
    from memory_system.domain.models.context_archive import ContextArchiveCreateInput

    messages = [
        _wm_message("msg_001", "first"),
        WorkingMemoryMessage(
            message_id="msg_002",
            role=MessageRole.ASSISTANT,
            content="second",
            estimated_tokens=7,
            timestamp=FIXED_NOW + 1,
        ),
    ]
    batch_key = f"{SESSION_ID}:msg_001:msg_002"
    input_data = ContextArchiveCreateInput(
        user_id=USER_ID,
        session_id=SESSION_ID,
        archive_batch_key=batch_key,
        base_compression_version=0,
        messages=messages,
    )
    document = archive_document_from_input(
        input=input_data,
        archive_id="00000000-0000-4000-8000-000000000001",
        created_time=FIXED_NOW,
    )
    assert document["user_id"] == USER_ID
    assert document["session_id"] == SESSION_ID
    assert document["archive_batch_key"] == batch_key
    raw_messages = document["messages"]
    assert isinstance(raw_messages, list)
    assert len(raw_messages) == 2
    for msg in raw_messages:
        assert set(msg.keys()) == {"message_id", "role", "content", "timestamp"}
        assert "estimated_tokens" not in msg


def test_archive_document_preserves_message_order() -> None:
    from memory_system.domain.models.context_archive import ContextArchiveCreateInput

    messages = [
        _wm_message("msg_m1", "one"),
        _wm_message("msg_m2", "two"),
        _wm_message("msg_m3", "three"),
    ]
    batch_key = f"{SESSION_ID}:msg_m1:msg_m3"
    input_data = ContextArchiveCreateInput(
        user_id=USER_ID,
        session_id=SESSION_ID,
        archive_batch_key=batch_key,
        base_compression_version=1,
        messages=messages,
    )
    document = archive_document_from_input(
        input=input_data,
        archive_id="00000000-0000-4000-8000-000000000002",
        created_time=FIXED_NOW,
    )
    raw_messages = document["messages"]
    assert isinstance(raw_messages, list)
    ids = [msg["message_id"] for msg in raw_messages]
    assert ids == ["msg_m1", "msg_m2", "msg_m3"]


@pytest.mark.parametrize("estimated_tokens", [0, 1, 10_000])
def test_estimated_tokens_never_in_archive_message(estimated_tokens: int) -> None:
    archive_msg = wm_message_to_archive_message(_wm_message(estimated_tokens=estimated_tokens))
    assert "estimated_tokens" not in archive_msg.model_dump()
