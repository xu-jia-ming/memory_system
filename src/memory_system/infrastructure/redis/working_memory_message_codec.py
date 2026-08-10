"""Redis List JSON codec for WorkingMemoryMessage (§1.2.1)."""

from __future__ import annotations

import json

from memory_system.domain.enums.working_memory import MessageRole
from memory_system.domain.models.working_memory import WorkingMemoryMessage


def message_to_json(message: WorkingMemoryMessage) -> str:
    """Serialize WorkingMemoryMessage to compact JSON with fixed field order."""
    payload = {
        "message_id": message.message_id,
        "role": message.role.value,
        "content": message.content,
        "estimated_tokens": message.estimated_tokens,
        "timestamp": message.timestamp,
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def json_to_message(payload: str) -> WorkingMemoryMessage:
    """Deserialize Redis List element JSON to WorkingMemoryMessage."""
    data = json.loads(payload)
    return WorkingMemoryMessage(
        message_id=data["message_id"],
        role=MessageRole(data["role"]),
        content=data["content"],
        estimated_tokens=int(data["estimated_tokens"]),
        timestamp=int(data["timestamp"]),
    )
