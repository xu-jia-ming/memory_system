"""EXT-007 retrieval index sync domain models."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from memory_system.domain.models.entity_alignment import EntityAlignmentSuccess
from memory_system.domain.models.extraction_task import MemoryExtractionTask
from memory_system.domain.models.graph_write import GraphWriteSuccess


class RetrievalIndexSyncOutcomeKind(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    SKIP_ALREADY_COMPLETED = "skip_already_completed"


class RetrievalIndexSyncInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    task_id: str
    archive_id: str
    user_id: str
    session_id: str | None
    graph_write_success: GraphWriteSuccess
    entity_alignment: EntityAlignmentSuccess


class MemoryIndexRow(BaseModel):
    """Internal Neo4j row for §2.2.4 document assembly (not persisted to ES)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    memory_id: str
    user_id: str
    memory_type: str
    status: str
    content: str
    predicate: str
    event_status: str | None
    latest_source_time: int | None
    updated_time: int
    subject_entity_id: str
    object_entity_id: str | None
    object_value: str | None
    subject_canonical_name: str | None
    subject_aliases: list[str]
    object_canonical_name: str | None
    object_aliases: list[str]


class MemoryIndexDocument(BaseModel):
    """Elasticsearch retrieval index document payload (§2.2.4)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    memory_id: str
    user_id: str
    memory_type: str
    status: str
    content: str
    search_text: str
    predicate: str
    event_status: str | None
    latest_source_time: int | None
    updated_time: int
    embedding: list[float] = Field(min_length=1024, max_length=1024)


class RetrievalIndexSyncSuccess(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    user_id: str
    archive_id: str
    synced_memory_count: int = Field(ge=0)
    omitted_alias_total: int = Field(ge=0)
    task: MemoryExtractionTask


class RetrievalIndexSyncFailure(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    error_code: Literal["retrieval_index_write_failed"] = "retrieval_index_write_failed"
    failed_stage: Literal["retrieval_index"] = "retrieval_index"
    message: str
    task: MemoryExtractionTask | None = None


class RetrievalIndexSyncSkip(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    reason: Literal["task_already_completed"] = "task_already_completed"
    task: MemoryExtractionTask


class RetrievalIndexSyncOutcome(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    outcome: RetrievalIndexSyncOutcomeKind
    success: RetrievalIndexSyncSuccess | None = None
    failure: RetrievalIndexSyncFailure | None = None
    skip: RetrievalIndexSyncSkip | None = None


class RetrievalIndexSyncAbort(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    kind: Literal["abort_without_terminal"] = "abort_without_terminal"
