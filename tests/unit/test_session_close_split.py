"""Unit tests for split_close_suffix_batches (STM-010)."""

from __future__ import annotations

import pytest

from memory_system.domain.enums.working_memory import MessageRole
from memory_system.domain.models.working_memory import WorkingMemoryMessage
from memory_system.domain.services.session_close_service import (
    SingleMessageExceedsArchiveCapError,
    split_close_suffix_batches,
)

FIXED_NOW = 1_700_000_000


def _message(mid: str, tokens: int) -> WorkingMemoryMessage:
    return WorkingMemoryMessage(
        message_id=mid,
        role=MessageRole.USER,
        content="x",
        estimated_tokens=tokens,
        timestamp=FIXED_NOW,
    )


def test_empty_messages_returns_empty() -> None:
    assert split_close_suffix_batches([], 100) == []


def test_single_batch_under_cap() -> None:
    messages = [_message("m1", 30), _message("m2", 40)]
    batches = split_close_suffix_batches(messages, 100)
    assert len(batches) == 1
    assert batches[0] == messages


def test_multiple_batches_by_cap() -> None:
    messages = [_message("m1", 60), _message("m2", 60), _message("m3", 30)]
    batches = split_close_suffix_batches(messages, 100)
    assert len(batches) == 2
    assert batches[0] == [messages[0]]
    assert batches[1] == [messages[1], messages[2]]


def test_exact_cap_boundary() -> None:
    messages = [_message("m1", 50), _message("m2", 50)]
    batches = split_close_suffix_batches(messages, 100)
    assert len(batches) == 1
    assert sum(m.estimated_tokens for m in batches[0]) == 100


def test_single_message_exceeds_cap_raises() -> None:
    messages = [_message("m1", 150)]
    with pytest.raises(SingleMessageExceedsArchiveCapError):
        split_close_suffix_batches(messages, 100)
