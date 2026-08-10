"""STM-001 public contract tests (no network, no Redis I/O)."""

from __future__ import annotations

from memory_system.domain.services.token_estimator import estimate_tokens
from memory_system.infrastructure.redis.keys import (
    working_memory_message_ids_key,
    working_memory_messages_key,
    working_memory_meta_key,
)

USER_ID = "user_001"
SESSION_ID = "session_001"


def test_estimate_tokens_deterministic_fixture() -> None:
    assert estimate_tokens("Hello 世界") == 4
    assert estimate_tokens("") == 0
    assert estimate_tokens("中文测试") == 5


def test_working_memory_key_literals_match_spec() -> None:
    assert working_memory_meta_key(USER_ID, SESSION_ID) == (
        "memory:working:user_001:session_001"
    )
    assert working_memory_messages_key(USER_ID, SESSION_ID) == (
        "memory:working:user_001:session_001:messages"
    )
    assert working_memory_message_ids_key(USER_ID, SESSION_ID) == (
        "memory:working:user_001:session_001:message_ids"
    )
