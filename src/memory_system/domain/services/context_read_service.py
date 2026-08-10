"""Context read domain service (single Lua atomic snapshot)."""

from __future__ import annotations

import json

import redis.asyncio as redis

from memory_system.domain.enums.context_read import ContextReadStatus
from memory_system.domain.models.context_read import (
    ContextReadInput,
    ContextReadResult,
    WorkingMemorySnapshot,
)
from memory_system.domain.models.working_memory import WorkingMemoryMessage
from memory_system.infrastructure.redis.context_read_repository import execute_context_read_lua
from memory_system.infrastructure.redis.working_memory_message_codec import json_to_message


class ContextReadFailure(Exception):
    """Raised when Lua succeeds but Python snapshot assembly fails (malformed message JSON)."""


async def read_working_memory_context(
    *,
    redis: redis.Redis,
    input: ContextReadInput,
) -> ContextReadResult:
    """Read Working Memory context via single read-only Lua snapshot."""
    lua_result = await execute_context_read_lua(
        redis=redis,
        user_id=input.user_id,
        session_id=input.session_id,
    )

    if isinstance(lua_result, ContextReadStatus):
        return ContextReadResult(status=lua_result, snapshot=None)

    compression_version_str, compressed_context, message_jsons = lua_result

    messages: list[WorkingMemoryMessage] = []
    try:
        for message_json in message_jsons:
            messages.append(json_to_message(message_json))
    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        raise ContextReadFailure(
            f"Failed to decode message JSON for session {input.session_id!r}"
        ) from exc

    snapshot = WorkingMemorySnapshot(
        compression_version=int(compression_version_str),
        compressed_context=compressed_context,
        messages=messages,
    )
    return ContextReadResult(status=ContextReadStatus.SUCCESS, snapshot=snapshot)
