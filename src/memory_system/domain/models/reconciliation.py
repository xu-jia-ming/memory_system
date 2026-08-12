"""EXT-005 reconciliation domain models (transient plan output)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from memory_system.domain.models.entity_alignment import EntityAlignmentSuccess
from memory_system.domain.models.extraction_llm import (
    ExtractionValidatedResult,
)


class ReconciliationOutcomeKind(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class ReconciliationAction(StrEnum):
    CREATE = "CREATE"
    MERGE = "MERGE"
    SUPERSEDE = "SUPERSEDE"
    CONFLICT = "CONFLICT"
    SKIP = "SKIP"


class ReasonCode(StrEnum):
    NEW_MEMORY = "new_memory"
    SAME_SEMANTIC_MEMORY = "same_semantic_memory"
    ADDITIONAL_EVIDENCE = "additional_evidence"
    EXPLICIT_CORRECTION = "explicit_correction"
    NEWER_VALUE = "newer_value"
    UNRESOLVED_CONTRADICTION = "unresolved_contradiction"
    DIFFERENT_EVENT_TIME = "different_event_time"
    NOT_DURABLE = "not_durable"
    INVALID_CANDIDATE = "invalid_candidate"


class ReconciliationErrorCode(StrEnum):
    GRAPH_QUERY_FAILED = "graph_query_failed"
    RECONCILIATION_PLAN_CONFLICT = "reconciliation_plan_conflict"
    LLM_TIMEOUT = "llm_timeout"
    LLM_REQUEST_FAILED = "llm_request_failed"
    LLM_INVALID_OUTPUT = "llm_invalid_output"


class ReconciliationInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    task_id: str
    archive_id: str
    user_id: str
    session_id: str | None
    extraction_result: ExtractionValidatedResult
    entity_alignment: EntityAlignmentSuccess


class AlignedMemoryCandidateView(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    candidate_index: int = Field(ge=0)
    memory_type: str
    content: str
    predicate: str
    object_value: str | None
    event_status: str | None
    start_time: str | None
    end_time: str | None
    original_time_text: str | None
    confidence: float = Field(ge=0.0, le=1.0)
    source_message_ids: list[str]
    candidate_source_time: int
    candidate_fingerprint: str
    subject_entity_id: str
    object_entity_id: str | None
    evidence_id: str


class PerCandidateDecision(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    candidate_index: int = Field(ge=0)
    candidate_fingerprint: str
    evidence_id: str
    action: ReconciliationAction
    target_memory_id: str | None
    reason_code: ReasonCode | None
    skip_reason: Literal["evidence_already_processed"] | None
    merged_content: str | None
    recalled_memory_count: int = Field(ge=0)
    aligned_memory_key: str | None


class PlannedExistingMemoryUpdate(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    target_memory_id: str
    aggregated_action: Literal["MERGE", "SUPERSEDE", "CONFLICT"]
    contributing_candidate_indices: list[int]
    contributing_evidence_ids: list[str]
    planned_merged_content: str | None
    planned_merged_confidence: float | None
    planned_latest_source_time: int | None
    increment_memory_version: bool
    planned_new_memory_id: str | None


class PlannedMemoryCreate(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    create_kind: Literal["create", "supersede_new", "conflict_new"]
    planned_memory_id: str
    aligned_memory_key: str | None
    supersedes_target_memory_id: str | None
    conflicts_with_target_memory_id: str | None
    memory_type: str
    planned_content: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str | None
    object_value: str | None
    event_status: str | None
    start_time: str | None
    end_time: str | None
    original_time_text: str | None
    planned_confidence: float
    planned_importance: float
    planned_latest_source_time: int
    initial_memory_version: Literal[1] = 1
    contributing_candidate_indices: list[int]
    contributing_evidence_ids: list[str]


class ReconciliationSuccess(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    user_id: str
    archive_id: str
    per_candidate_decisions: list[PerCandidateDecision]
    existing_memory_update_plans: list[PlannedExistingMemoryUpdate]
    new_memory_create_plans: list[PlannedMemoryCreate]


class ReconciliationFailure(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    error_code: ReconciliationErrorCode
    failed_stage: Literal["reconciliation"] = "reconciliation"


class ReconciliationOutcome(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    outcome: ReconciliationOutcomeKind
    success: ReconciliationSuccess | None = None
    failure: ReconciliationFailure | None = None


class ReconciliationAbort(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    kind: Literal["abort_without_terminal"] = "abort_without_terminal"


class ReconciliationLlmInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    candidate: dict[str, object]
    existing_memories: list[dict[str, object]]


class ReconciliationLlmOutput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    action: ReconciliationAction
    target_memory_id: str | None
    reason_code: ReasonCode
    merged_content: str | None
