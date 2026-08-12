"""EXT-003 extraction LLM domain models (strict durable result shape)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from memory_system.domain.models.extraction_preprocessing import ExtractionReadyArchive

ENTITY_TYPES = frozenset(
    {"person", "organization", "product", "project", "location", "concept", "other"}
)
MEMORY_TYPES = frozenset({"fact", "preference", "event", "profile"})
EVENT_STATUSES = frozenset({"occurred", "ongoing", "planned", "cancelled", "unknown"})
RESERVED_USER_ENTITY_ID = "user"

AUTHORIZED_ENTITY_FIELDS = frozenset({"local_entity_id", "name", "type", "aliases"})
AUTHORIZED_MEMORY_FIELDS = frozenset(
    {
        "memory_type",
        "content",
        "subject_entity_id",
        "predicate",
        "object_entity_id",
        "object_value",
        "event_status",
        "start_time",
        "end_time",
        "original_time_text",
        "confidence",
        "source_message_ids",
        "candidate_source_time",
        "candidate_fingerprint",
    }
)


class ExtractionLlmOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class ExtractionEntityCandidate(BaseModel):
    """Validated entity candidate for durable extraction_result."""

    model_config = ConfigDict(strict=True, extra="forbid")

    local_entity_id: str
    name: str
    type: Literal[
        "person",
        "organization",
        "product",
        "project",
        "location",
        "concept",
        "other",
    ]
    aliases: list[str]


class ExtractionMemoryCandidate(BaseModel):
    """Validated memory candidate with application-derived metadata."""

    model_config = ConfigDict(strict=True, extra="forbid")

    memory_type: Literal["fact", "preference", "event", "profile"]
    content: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str | None
    object_value: str | None
    event_status: Literal["occurred", "ongoing", "planned", "cancelled", "unknown"] | None
    start_time: str | None
    end_time: str | None
    original_time_text: str | None
    confidence: float = Field(ge=0.0, le=1.0)
    source_message_ids: list[str]
    candidate_source_time: int
    candidate_fingerprint: str


class ExtractionValidatedResult(BaseModel):
    """Complete validated extraction result ready for persistence."""

    model_config = ConfigDict(strict=True, extra="forbid")

    entities: list[ExtractionEntityCandidate]
    memories: list[ExtractionMemoryCandidate]

    def is_both_empty(self) -> bool:
        return not self.entities and not self.memories

    def to_durable_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ExtractionLlmFailure(BaseModel):
    model_config = ConfigDict(strict=True)

    error_code: Literal["llm_timeout", "llm_request_failed", "llm_invalid_output"]
    failed_stage: Literal["llm_extraction"] = "llm_extraction"
    attempt_count: int = Field(ge=1, le=2)


class ExtractionLlmSuccess(BaseModel):
    model_config = ConfigDict(strict=True)

    result: ExtractionValidatedResult
    attempt_count: int = Field(ge=1, le=2)


class ExtractionLlmResult(BaseModel):
    model_config = ConfigDict(strict=True)

    outcome: ExtractionLlmOutcome
    success: ExtractionLlmSuccess | None = None
    failure: ExtractionLlmFailure | None = None


class ExtractionLlmInput(BaseModel):
    """Prepared extraction input from ExtractionReadyArchive."""

    model_config = ConfigDict(strict=True)

    archive: ExtractionReadyArchive
    task_id: str
    archive_id: str
    user_id: str
