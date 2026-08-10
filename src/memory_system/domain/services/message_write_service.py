"""Message write domain service (Token pre-check + Lua orchestration)."""

from __future__ import annotations

import json
import time
from collections.abc import Callable

import redis.asyncio as redis

from memory_system.domain.enums.message_write import MessageWriteStatus
from memory_system.domain.models.message_write import MessageWriteInput, MessageWriteResult
from memory_system.domain.models.working_memory import WorkingMemoryMessage
from memory_system.domain.services.token_estimator import estimate_tokens
from memory_system.infrastructure.redis.keys import working_memory_meta_key
from memory_system.infrastructure.redis.message_write_repository import execute_message_write_lua
from memory_system.infrastructure.redis.working_memory_message_codec import message_to_json
from memory_system.settings.models import ContextSettings

Clock = Callable[[], int]


class MessageWriteValidationError(ValueError):
    """Raised when service-layer input validation fails before Lua."""


class MessageWriteIdMismatchError(MessageWriteValidationError):
    """Raised when serialized JSON message_id does not match the Lua ARGV message_id."""


def _default_clock() -> int:
    return int(time.time())


def _validate_content(content: str) -> None:
    if not content or not content.strip():
        raise MessageWriteValidationError("content must not be empty")


def _assert_serialized_message_id_matches(message_json: str, message_id: str) -> None:
    parsed = json.loads(message_json)
    serialized_id = parsed.get("message_id")
    if serialized_id != message_id:
        raise MessageWriteIdMismatchError(
            f"serialized message_id {serialized_id!r} does not match {message_id!r}"
        )


async def write_message(
    *,
    redis: redis.Redis,
    input: MessageWriteInput,
    context: ContextSettings,
    clock: Clock | None = None,
) -> MessageWriteResult:
    """Write a message to Working Memory with Python token pre-check and Lua atomicity."""
    _validate_content(input.content)

    message_estimated_tokens = estimate_tokens(input.content)
    max_message_tokens = context.max_message_estimated_tokens
    if message_estimated_tokens > max_message_tokens:
        return MessageWriteResult(
            status=MessageWriteStatus.MESSAGE_TOO_LARGE,
            message_id=input.message_id,
        )

    now = (clock or _default_clock)()
    timestamp = input.timestamp if input.timestamp is not None else now

    message = WorkingMemoryMessage(
        message_id=input.message_id,
        role=input.role,
        content=input.content,
        estimated_tokens=message_estimated_tokens,
        timestamp=timestamp,
    )
    message_json = message_to_json(message)
    _assert_serialized_message_id_matches(message_json, input.message_id)

    lua_status = await execute_message_write_lua(
        redis=redis,
        user_id=input.user_id,
        session_id=input.session_id,
        message_id=input.message_id,
        message_json=message_json,
        message_estimated_tokens=message_estimated_tokens,
        max_wm_tokens=context.max_working_memory_estimated_tokens,
        updated_time=now,
    )

    if lua_status == MessageWriteStatus.SUCCESS:
        meta_key = working_memory_meta_key(input.user_id, input.session_id)
        new_total_raw = await redis.hget(meta_key, "estimated_tokens")
        new_total = int(new_total_raw) if new_total_raw is not None else None
        return MessageWriteResult(
            status=lua_status,
            message_id=input.message_id,
            estimated_tokens=new_total,
            message_estimated_tokens=message_estimated_tokens,
        )

    return MessageWriteResult(
        status=lua_status,
        message_id=input.message_id,
    )
