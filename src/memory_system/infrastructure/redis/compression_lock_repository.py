"""Compression lock Redis repository — SET NX EX + compare-and-del (STM-006)."""

from __future__ import annotations

import uuid
from collections.abc import Callable

import redis.asyncio as redis

from memory_system.infrastructure.redis.keys import compression_lock_key

TokenFactory = Callable[[], str]

_RELEASE_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""


def _default_token_factory() -> str:
    return str(uuid.uuid4())


async def acquire_compression_lock(
    redis_client: redis.Redis,
    *,
    user_id: str,
    session_id: str,
    ttl_seconds: int,
    token_factory: TokenFactory | None = None,
) -> str | None:
    """Acquire lock via SET NX EX. Returns owner token on success, else None."""
    token = (token_factory or _default_token_factory)()
    key = compression_lock_key(user_id, session_id)
    acquired = await redis_client.set(key, token, nx=True, ex=ttl_seconds)
    if acquired:
        return token
    return None


async def release_compression_lock(
    redis_client: redis.Redis,
    *,
    user_id: str,
    session_id: str,
    token: str,
) -> bool:
    """Release lock only when current value equals owner token (single Lua)."""
    key = compression_lock_key(user_id, session_id)
    script = redis_client.register_script(_RELEASE_LUA)
    deleted = await script(keys=[key], args=[token])
    return int(deleted) == 1
