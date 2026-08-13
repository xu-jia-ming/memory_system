"""HTTP schemas for POST /api/v1/memory/retrieval (§2.2.5 / §2.2.12)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RetrievalRequest(BaseModel):
    """Memory retrieval request body."""

    model_config = ConfigDict(strict=True, extra="forbid")

    user_id: str = Field(min_length=1)
    query: str
    memory_types: list[str] | None = None
    top_k: int | None = None
    include_conflicted: bool = False
    include_history: bool = False
    graph_expand: bool = True


class RetrievalSubject(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    entity_id: str
    name: str


class RetrievalObject(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    entity_id: str | None
    name: str | None
    value: str | None


class RetrievalMemoryItem(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    memory_id: str
    memory_type: str
    content: str
    subject: RetrievalSubject
    predicate: str
    object: RetrievalObject
    status: str
    event_status: str | None
    start_time: int | None
    end_time: int | None
    confidence: float
    importance: float
    latest_source_time: int | None
    score: float
    retrieval_source: list[Literal["bm25", "vector", "graph"]]
    source_message_ids: list[str]
    evidence_count: int


class RetrievalResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    retrieval_mode: Literal["hybrid", "bm25_only", "vector_only", "none"]
    warnings: list[str]
    memories: list[RetrievalMemoryItem]
