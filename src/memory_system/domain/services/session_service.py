"""Session creation domain service."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from typing import Literal

import redis.asyncio as redis

from memory_system.infrastructure.redis.working_memory_repository import (
    create_working_memory_session,
)

Clock = Callable[[], int]
CreatedStatus = Literal["created"]


def _default_clock() -> int:
    return int(time.time())


async def create_session(
    *,
    redis: redis.Redis,
    user_id: str,
    clock: Clock | None = None,
) -> tuple[str, CreatedStatus]:
    """Create a new session with server-generated UUID v4 and WM meta Hash."""
    session_id = str(uuid.uuid4())
    now = (clock or _default_clock)()
    await create_working_memory_session(
        redis=redis,
        user_id=user_id,
        session_id=session_id,
        now=now,
    )
    return session_id, "created"
