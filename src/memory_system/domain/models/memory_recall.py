"""EXT-005 Memory read-only snapshot models (§2.1.9 / §2.1.11 recall)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

MEMORY_LABEL = "Memory"

MEMORY_PROPERTY_NAMES: frozenset[str] = frozenset(
    {
        "memory_id",
        "user_id",
        "memory_type",
        "content",
        "subject_entity_id",
        "predicate",
        "object_entity_id",
        "object_value",
        "status",
        "event_status",
        "start_time",
        "end_time",
        "original_time_text",
        "confidence",
        "latest_source_time",
    }
)


class MemoryNodeSnapshot(BaseModel):
    """§2.1.9 Memory read-only snapshot for reconciliation recall."""

    model_config = ConfigDict(strict=True, extra="forbid")

    memory_id: str
    user_id: str
    memory_type: str
    content: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str | None
    object_value: str | None
    status: str
    event_status: str | None
    start_time: str | None
    end_time: str | None
    original_time_text: str | None
    confidence: float = Field(ge=0.0, le=1.0)
    latest_source_time: int | None = None
