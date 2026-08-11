"""Working Memory Redis repository (meta Hash I/O)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import redis.asyncio as redis

from memory_system.domain.enums.working_memory import SessionStatus
from memory_system.domain.models.working_memory import WorkingMemoryMeta
from memory_system.infrastructure.redis.keys import working_memory_meta_key
from memory_system.infrastructure.redis.working_memory_codec import (
    hash_fields_to_meta,
    meta_to_hash_fields,
)


async def create_working_memory_session(
    *,
    redis: redis.Redis,
    user_id: str,
    session_id: str,
    now: int,
) -> WorkingMemoryMeta:
    """Initialize a new Working Memory meta Hash via unconditional HSET."""
    meta = WorkingMemoryMeta(
        user_id=user_id,
        session_id=session_id,
        compressed_context="",
        estimated_tokens=0,
        compression_version=0,
        status=SessionStatus.ACTIVE,
        pending_archive_id=None,
        pending_archive_batch_key=None,
        pending_archive_message_count=0,
        pending_archive_estimated_tokens=0,
        created_time=now,
        updated_time=now,
    )
    key = working_memory_meta_key(user_id, session_id)
    fields = meta_to_hash_fields(meta)
    await redis.hset(key, mapping=fields)  # type: ignore[arg-type]
    return meta


async def get_working_memory_meta(
    redis: redis.Redis,
    user_id: str,
    session_id: str,
) -> WorkingMemoryMeta | None:
    """Read Working Memory meta Hash; return None when session does not exist."""
    key = working_memory_meta_key(user_id, session_id)
    fields_raw = await redis.hgetall(key)
    if not fields_raw:
        return None
    fields = cast(Mapping[str, str], fields_raw)
    return hash_fields_to_meta(fields)
