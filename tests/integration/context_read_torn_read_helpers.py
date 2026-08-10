"""Test-only helpers for I12 torn-read proof (NOT production code)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import redis.asyncio as aioredis

from memory_system.domain.enums.working_memory import MessageRole
from memory_system.domain.models.working_memory import WorkingMemoryMessage
from memory_system.infrastructure.redis.keys import (
    working_memory_messages_key,
    working_memory_meta_key,
)
from memory_system.infrastructure.redis.working_memory_message_codec import message_to_json

FIXED_NOW = 1_700_000_000

# Canonical states: all fields pairwise distinct (V0/C0/M0 vs V1/C1/M1).
V0 = 0
V1 = 1
C0 = "old-summary-context"
C1 = "new-summary-context"


def _make_message(message_id: str, content: str) -> WorkingMemoryMessage:
    return WorkingMemoryMessage(
        message_id=message_id,
        role=MessageRole.USER,
        content=content,
        estimated_tokens=len(content),
        timestamp=FIXED_NOW,
    )


M0_MESSAGES: list[WorkingMemoryMessage] = [
    _make_message("old-msg-1", "old-content-alpha"),
    _make_message("old-msg-2", "old-content-beta"),
    _make_message("old-msg-3", "old-content-gamma"),
]

M1_MESSAGES: list[WorkingMemoryMessage] = [
    _make_message("new-msg-1", "new-content-only"),
]


@dataclass(frozen=True)
class CanonicalState:
    """Canonical WM snapshot for torn-read I12."""

    compression_version: int
    compressed_context: str
    messages: tuple[WorkingMemoryMessage, ...]


OLD_STATE = CanonicalState(
    compression_version=V0,
    compressed_context=C0,
    messages=tuple(M0_MESSAGES),
)

NEW_STATE = CanonicalState(
    compression_version=V1,
    compressed_context=C1,
    messages=tuple(M1_MESSAGES),
)

FORBIDDEN_HYBRID = CanonicalState(
    compression_version=V0,
    compressed_context=C1,
    messages=tuple(M1_MESSAGES),
)


_ATOMIC_STATE_MUTATOR_LUA = """
local meta_key = KEYS[1]
local messages_key = KEYS[2]
redis.call('HSET', meta_key, 'compression_version', ARGV[1])
redis.call('HSET', meta_key, 'compressed_context', ARGV[2])
redis.call('DEL', messages_key)
for i = 3, #ARGV do
  redis.call('RPUSH', messages_key, ARGV[i])
end
return 'ok'
"""


def snapshot_matches(
    *,
    compression_version: int | str,
    compressed_context: str,
    messages: list[WorkingMemoryMessage] | list[str],
    canonical: CanonicalState,
) -> bool:
    """Return True when snapshot fields match a canonical state."""
    version = int(compression_version)
    if version != canonical.compression_version:
        return False
    if compressed_context != canonical.compressed_context:
        return False
    if len(messages) != len(canonical.messages):
        return False
    for actual, expected in zip(messages, canonical.messages, strict=True):
        if isinstance(actual, str):
            if message_to_json(expected) != actual:
                return False
        elif actual != expected:
            return False
    return True


async def apply_canonical_state(
    redis: aioredis.Redis,
    *,
    user_id: str,
    session_id: str,
    state: CanonicalState,
) -> None:
    """Atomically apply a canonical WM state via test-only Lua (single EVAL)."""
    meta_key = working_memory_meta_key(user_id, session_id)
    messages_key = working_memory_messages_key(user_id, session_id)
    message_jsons = [message_to_json(message) for message in state.messages]
    args = [str(state.compression_version), state.compressed_context, *message_jsons]
    script = redis.register_script(_ATOMIC_STATE_MUTATOR_LUA)
    await script(keys=[meta_key, messages_key], args=args)


async def toggle_canonical_state(
    redis: aioredis.Redis,
    *,
    user_id: str,
    session_id: str,
    current: CanonicalState,
) -> CanonicalState:
    """Toggle OLD_STATE <-> NEW_STATE atomically."""
    next_state = NEW_STATE if current is OLD_STATE else OLD_STATE
    await apply_canonical_state(
        redis,
        user_id=user_id,
        session_id=session_id,
        state=next_state,
    )
    return next_state


@dataclass
class BrokenSplitReadSnapshot:
    compression_version: str | None
    compressed_context: str | None
    messages: list[str]


async def broken_split_read_with_barrier(
    redis: aioredis.Redis,
    *,
    user_id: str,
    session_id: str,
    version_read_event: asyncio.Event,
    mutator_done_event: asyncio.Event,
) -> BrokenSplitReadSnapshot:
    """Deterministic split-reader: HGET version → pause → resume → HGET context + LRANGE."""
    meta_key = working_memory_meta_key(user_id, session_id)
    messages_key = working_memory_messages_key(user_id, session_id)

    compression_version_raw = await redis.hget(meta_key, "compression_version")
    version_read_event.set()
    await mutator_done_event.wait()

    compressed_context_raw = await redis.hget(meta_key, "compressed_context")
    messages_raw = await redis.lrange(messages_key, 0, -1)
    return BrokenSplitReadSnapshot(
        compression_version=(
            str(compression_version_raw)
            if compression_version_raw is not None
            else None
        ),
        compressed_context=(
            str(compressed_context_raw)
            if compressed_context_raw is not None
            else ""
        ),
        messages=[str(item) for item in messages_raw],
    )


def composed_forbidden_hybrid_assertion(snapshot: BrokenSplitReadSnapshot) -> dict[str, Any]:
    """Build composed snapshot dict for FORBIDDEN_HYBRID assertion."""
    return {
        "compression_version": snapshot.compression_version,
        "compressed_context": snapshot.compressed_context or "",
        "messages": snapshot.messages,
    }
