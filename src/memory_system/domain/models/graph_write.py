"""EXT-006 graph write domain models (transient plan + outcome)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from memory_system.domain.models.entity_alignment import EntityAlignmentSuccess
from memory_system.domain.models.extraction_llm import ExtractionValidatedResult
from memory_system.domain.models.reconciliation import ReconciliationSuccess

EVIDENCE_LABEL = "Evidence"

EVIDENCE_PROPERTY_NAMES: frozenset[str] = frozenset(
    {
        "evidence_id",
        "user_id",
        "archive_id",
        "session_id",
        "source_message_ids",
        "source_time_start",
        "source_time_end",
        "extracted_content",
        "prompt_version",
        "created_time",
    }
)


class GraphWriteOutcomeKind(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class GraphWriteErrorCode(StrEnum):
    GRAPH_WRITE_FAILED = "graph_write_failed"
    MEMORY_SEARCH_TEXT_TOO_LONG = "memory_search_text_too_long"


class GraphWriteInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    task_id: str
    archive_id: str
    user_id: str
    session_id: str | None
    extraction_result: ExtractionValidatedResult
    entity_alignment: EntityAlignmentSuccess
    reconciliation: ReconciliationSuccess


class IndexSyncMemoryEntry(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    memory_id: str
    core_search_text: str
    token_count: int = Field(ge=0)


class GraphWriteSuccess(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    user_id: str
    archive_id: str
    skipped_graph_write: bool
    index_sync_memory_set: list[IndexSyncMemoryEntry]


class GraphWriteFailure(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    error_code: Literal["graph_write_failed", "memory_search_text_too_long"]
    failed_stage: Literal["graph_write"] = "graph_write"


class GraphWriteOutcome(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    outcome: GraphWriteOutcomeKind
    success: GraphWriteSuccess | None = None
    failure: GraphWriteFailure | None = None


class GraphWriteAbort(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    kind: Literal["abort_without_terminal"] = "abort_without_terminal"


class ReferencedEntityWritePlan(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    entity_key: str
    entity_id: str
    user_id: str
    entity_type: str
    canonical_name: str
    normalized_name: str
    aliases: list[str]
    planned_create: bool


class EntityWriteRow(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    entity_key: str
    entity_id: str
    user_id: str
    entity_type: str
    canonical_name: str
    normalized_name: str
    aliases: list[str]
    created_time: int
    updated_time: int


class MemoryCreateRow(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    memory_id: str
    user_id: str
    memory_type: str
    content: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str | None
    object_value: str | None
    status: Literal["active", "conflicted"] = "active"
    event_status: str | None
    start_time: str | None
    end_time: str | None
    original_time_text: str | None
    confidence: float = Field(ge=0.0, le=1.0)
    importance: float = Field(ge=0.0, le=1.0)
    latest_source_time: int
    abstraction_level: Literal[0] = 0
    retrieval_count: Literal[0] = 0
    memory_version: Literal[1] = 1
    first_seen_time: int
    last_seen_time: int
    created_time: int
    updated_time: int
    last_retrieved_time: None = None
    last_consolidated_time: None = None
    supersedes_target_memory_id: str | None
    conflicts_with_target_memory_id: str | None


class MemoryUpdateRow(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    target_memory_id: str
    user_id: str
    planned_merged_content: str | None
    planned_merged_confidence: float | None
    planned_latest_source_time: int | None
    increment_memory_version: bool
    aggregated_action: Literal["MERGE", "SUPERSEDE", "CONFLICT"]
    updated_time: int
    last_seen_time: int
    status: str | None


class EvidenceWriteRow(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    evidence_id: str
    user_id: str
    archive_id: str
    session_id: str
    memory_id: str
    source_message_ids: list[str]
    source_time_start: int
    source_time_end: int
    extracted_content: str
    prompt_version: str
    created_time: int


class ImmutableGraphWritePlan(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    user_id: str
    archive_id: str
    entity_rows: list[EntityWriteRow]
    memory_create_rows: list[MemoryCreateRow]
    memory_update_rows: list[MemoryUpdateRow]
    evidence_rows: list[EvidenceWriteRow]
    index_sync_memory_set: list[IndexSyncMemoryEntry]
