"""Working Memory Redis key templates (§1.2.1; no client I/O)."""

from __future__ import annotations

_WORKING_MEMORY_PREFIX = "memory:working"


def working_memory_meta_key(user_id: str, session_id: str) -> str:
    """Return the Hash key for session metadata."""
    return f"{_WORKING_MEMORY_PREFIX}:{user_id}:{session_id}"


def working_memory_messages_key(user_id: str, session_id: str) -> str:
    """Return the List key for session messages."""
    return f"{_WORKING_MEMORY_PREFIX}:{user_id}:{session_id}:messages"


def working_memory_message_ids_key(user_id: str, session_id: str) -> str:
    """Return the Set key for session message IDs."""
    return f"{_WORKING_MEMORY_PREFIX}:{user_id}:{session_id}:message_ids"
