"""Kafka ``context.archive.created`` event model (§1.2.4; six fields only)."""

from __future__ import annotations

import json
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field

ARCHIVE_CREATED_EVENT_TYPE: Final[str] = "context.archive.created"

ARCHIVE_CREATED_EVENT_FIELD_NAMES: Final[tuple[str, ...]] = (
    "event_id",
    "event_type",
    "archive_id",
    "user_id",
    "session_id",
    "created_time",
)


class ArchiveCreatedEvent(BaseModel):
    """Exact §1.2.4 schema — no archive_batch_key / base_compression_version."""

    model_config = ConfigDict(strict=True)

    event_id: str
    event_type: str = Field(default=ARCHIVE_CREATED_EVENT_TYPE)
    archive_id: str
    user_id: str
    session_id: str
    created_time: int

    def to_json_bytes(self) -> bytes:
        """Serialize to compact UTF-8 JSON with exactly the six approved fields."""
        payload: dict[str, Any] = {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "archive_id": self.archive_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "created_time": self.created_time,
        }
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
