"""RET-003 Neo4j authoritative memory and entity read snapshots (§2.1.9 / §2.2.10)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RetrievalEntitySnapshot(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    entity_id: str
    canonical_name: str
    aliases: list[str]
    entity_type: str
    normalized_name: str


class RetrievalMemorySnapshot(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    memory_id: str
    user_id: str
    memory_type: str
    status: str
    content: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str | None
    object_value: str | None
    event_status: str | None
    start_time: int | None
    end_time: int | None
    original_time_text: str | None
    importance: float = Field(ge=0.0)
    confidence: float = Field(ge=0.0, le=1.0)
    retrieval_count: int = Field(ge=0)
    last_retrieved_time: int | None
    latest_source_time: int | None
    updated_time: int
    subject_entity: RetrievalEntitySnapshot | None
    object_entity: RetrievalEntitySnapshot | None
