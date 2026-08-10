"""Unit tests for WorkingMemoryMessage Redis JSON codec."""

from __future__ import annotations

import json

from memory_system.domain.enums.working_memory import MessageRole
from memory_system.domain.models.working_memory import WorkingMemoryMessage
from memory_system.infrastructure.redis.working_memory_message_codec import (
    json_to_message,
    message_to_json,
)

MESSAGE_ID = "123e4567-e89b-42d3-a456-426614174000"
TIMESTAMP = 1_700_000_000


def test_message_to_json_field_order_and_role_literals() -> None:
    message = WorkingMemoryMessage(
        message_id=MESSAGE_ID,
        role=MessageRole.USER,
        content="Hello",
        estimated_tokens=2,
        timestamp=TIMESTAMP,
    )
    payload = message_to_json(message)
    assert payload == (
        '{"message_id":"123e4567-e89b-42d3-a456-426614174000",'
        '"role":"user","content":"Hello","estimated_tokens":2,"timestamp":1700000000}'
    )

    assistant = WorkingMemoryMessage(
        message_id=MESSAGE_ID,
        role=MessageRole.ASSISTANT,
        content="Hi",
        estimated_tokens=1,
        timestamp=TIMESTAMP,
    )
    assistant_payload = message_to_json(assistant)
    parsed = json.loads(assistant_payload)
    assert parsed["role"] == "assistant"


def test_json_to_message_round_trip() -> None:
    original = WorkingMemoryMessage(
        message_id=MESSAGE_ID,
        role=MessageRole.USER,
        content="世界",
        estimated_tokens=3,
        timestamp=TIMESTAMP,
    )
    restored = json_to_message(message_to_json(original))
    assert restored == original
