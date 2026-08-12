"""EXT-004 entity alignment domain models (transient alignment output)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from memory_system.domain.models.extraction_llm import ExtractionEntityCandidate

ENTITY_LABEL = "Entity"

ENTITY_PROPERTY_NAMES: frozenset[str] = frozenset(
    {
        "entity_id",
        "user_id",
        "entity_key",
        "entity_type",
        "canonical_name",
        "normalized_name",
        "aliases",
    }
)


class EntityAlignmentOutcomeKind(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class EntityMatchKind(StrEnum):
    RESERVED_USER_EXISTING = "reserved_user_existing"
    RESERVED_USER_PLANNED_CREATE = "reserved_user_planned_create"
    ENTITY_KEY_EXACT = "entity_key_exact"
    CANONICAL_OR_ALIAS_EXACT = "canonical_or_alias_exact"
    PLANNED_CREATE = "planned_create"


class EntityNodeSnapshot(BaseModel):
    """§2.1.9 Entity read-only snapshot for alignment."""

    model_config = ConfigDict(strict=True, extra="forbid")

    entity_id: str
    user_id: str
    entity_key: str
    entity_type: str
    canonical_name: str
    normalized_name: str
    aliases: list[str]


class PlannedEntityAliasMerge(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    normalized_candidate_aliases: list[str]
    existing_aliases: list[str]
    planned_aliases: list[str]
    omitted_alias_count: int = Field(ge=0)
    canonical_name_replaced: Literal[False] = False


class AlignedEntity(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    local_entity_id: str
    entity_id: str
    match_kind: EntityMatchKind
    entity_type: str
    canonical_name: str
    normalized_name: str
    entity_key: str
    planned_alias_merge: PlannedEntityAliasMerge
    existing_entity: EntityNodeSnapshot | None
    planned_create: bool


class EntityAlignmentSuccess(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    user_id: str
    alignments: list[AlignedEntity]

    def local_entity_id_map(self) -> dict[str, str]:
        return {item.local_entity_id: item.entity_id for item in self.alignments}


class EntityAlignmentFailure(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    error_code: Literal["entity_alignment_failed"] = "entity_alignment_failed"
    failed_stage: Literal["entity_alignment"] = "entity_alignment"


class EntityAlignmentOutcome(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    outcome: EntityAlignmentOutcomeKind
    success: EntityAlignmentSuccess | None = None
    failure: EntityAlignmentFailure | None = None


class EntityAlignmentAbort(BaseModel):
    """Non-terminal abort when alignment preconditions are not met."""

    model_config = ConfigDict(strict=True, extra="forbid")

    kind: Literal["abort_without_terminal"] = "abort_without_terminal"


class EntityAlignmentInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    task_id: str
    archive_id: str
    user_id: str
    entities: list[ExtractionEntityCandidate]
    referenced_local_entity_ids: set[str]
