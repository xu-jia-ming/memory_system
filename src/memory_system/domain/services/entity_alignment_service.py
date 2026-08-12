"""EXT-004 deterministic entity alignment service (read-only, no LLM)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any, Protocol

import structlog
from pydantic import ValidationError
from pymongo import AsyncMongoClient

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.domain.models.entity_alignment import (
    AlignedEntity,
    EntityAlignmentAbort,
    EntityAlignmentFailure,
    EntityAlignmentInput,
    EntityAlignmentOutcome,
    EntityAlignmentOutcomeKind,
    EntityAlignmentSuccess,
    EntityMatchKind,
    EntityNodeSnapshot,
    PlannedEntityAliasMerge,
)
from memory_system.domain.models.extraction_llm import (
    RESERVED_USER_ENTITY_ID,
    ExtractionEntityCandidate,
    ExtractionMemoryCandidate,
    ExtractionValidatedResult,
)
from memory_system.domain.services.entity_key import (
    build_user_entity_id,
    compute_entity_key,
    normalize_entity_alias,
    normalize_entity_name,
    planned_user_entity_fields,
)
from memory_system.infrastructure.mongodb import extraction_task_repository as task_repo
from memory_system.infrastructure.neo4j.entity_alignment_repository import (
    EntityAlignmentRepository,
    EntityGraphDataError,
    SecondaryMatchCandidate,
)

_logger = structlog.get_logger(__name__)

EntityIdFactory = Callable[[], str]


class EntityAlignmentReadRepository(Protocol):
    async def find_user_entity(
        self, user_id: str, *, user_entity_id: str
    ) -> EntityNodeSnapshot | None: ...

    async def find_by_entity_keys(
        self, user_id: str, entity_keys: list[str]
    ) -> dict[str, EntityNodeSnapshot]: ...

    async def find_secondary_match_candidates(
        self, user_id: str, candidates: list[SecondaryMatchCandidate]
    ) -> dict[str, list[EntityNodeSnapshot]]: ...


def collect_referenced_local_entity_ids(
    memories: list[ExtractionMemoryCandidate],
) -> set[str]:
    referenced: set[str] = set()
    for memory in memories:
        referenced.add(memory.subject_entity_id)
        if memory.object_entity_id is not None:
            referenced.add(memory.object_entity_id)
    return referenced


def build_alignment_input(
    *,
    task_id: str,
    archive_id: str,
    user_id: str,
    validated: ExtractionValidatedResult,
) -> EntityAlignmentInput:
    return EntityAlignmentInput(
        task_id=task_id,
        archive_id=archive_id,
        user_id=user_id,
        entities=validated.entities,
        referenced_local_entity_ids=collect_referenced_local_entity_ids(validated.memories),
    )


def _normalize_candidate_aliases(aliases: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        value = normalize_entity_alias(alias)
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    normalized.sort()
    return normalized


def _plan_alias_merge(
    *,
    existing_aliases: list[str],
    candidate_aliases: list[str],
    max_stored_entity_alias_count: int,
) -> PlannedEntityAliasMerge:
    normalized_candidate_aliases = _normalize_candidate_aliases(candidate_aliases)
    planned = list(existing_aliases)
    existing_set = set(existing_aliases)
    omitted_alias_count = 0
    for alias in normalized_candidate_aliases:
        if alias in existing_set:
            continue
        if len(planned) >= max_stored_entity_alias_count:
            omitted_alias_count += 1
            continue
        planned.append(alias)
        existing_set.add(alias)
    return PlannedEntityAliasMerge(
        normalized_candidate_aliases=normalized_candidate_aliases,
        existing_aliases=list(existing_aliases),
        planned_aliases=planned,
        omitted_alias_count=omitted_alias_count,
    )


def _secondary_hits(
    snapshots: list[EntityNodeSnapshot],
    normalized_name: str,
) -> list[EntityNodeSnapshot]:
    hits: list[EntityNodeSnapshot] = []
    for snapshot in snapshots:
        if snapshot.normalized_name == normalized_name:
            hits.append(snapshot)
            continue
        for alias in snapshot.aliases:
            if normalize_entity_alias(alias) == normalized_name:
                hits.append(snapshot)
                break
    return hits


class EntityAlignmentService:
    """Deterministic entity alignment over persisted extraction_result."""

    def __init__(
        self,
        repository: EntityAlignmentReadRepository,
        *,
        max_stored_entity_alias_count: int = 50,
        entity_id_factory: EntityIdFactory | None = None,
    ) -> None:
        self._repository = repository
        self._max_stored_entity_alias_count = max_stored_entity_alias_count
        self._entity_id_factory = entity_id_factory or (lambda: str(uuid.uuid4()))

    async def align(
        self,
        alignment_input: EntityAlignmentInput,
        *,
        attempt_count: int | None = None,
    ) -> EntityAlignmentOutcome:
        try:
            alignments = await self._align_entities(alignment_input)
            return EntityAlignmentOutcome(
                outcome=EntityAlignmentOutcomeKind.SUCCESS,
                success=EntityAlignmentSuccess(
                    user_id=alignment_input.user_id,
                    alignments=alignments,
                ),
                failure=None,
            )
        except EntityGraphDataError:
            return self._failure_outcome(alignment_input, attempt_count=attempt_count)
        except Exception:
            return self._failure_outcome(alignment_input, attempt_count=attempt_count)

    async def load_from_persisted_task(
        self,
        mongodb: AsyncMongoClient[Any],
        archive_id: str,
    ) -> EntityAlignmentOutcome | EntityAlignmentAbort:
        task = await task_repo.find_extraction_task_by_archive_id(mongodb, archive_id)
        if task is None:
            return EntityAlignmentAbort()
        if task.status != ExtractionTaskStatus.PROCESSING or task.extraction_result is None:
            return EntityAlignmentAbort()
        try:
            validated = ExtractionValidatedResult.model_validate(task.extraction_result)
        except ValidationError:
            return EntityAlignmentAbort()
        alignment_input = build_alignment_input(
            task_id=task.task_id,
            archive_id=task.archive_id,
            user_id=task.user_id,
            validated=validated,
        )
        return await self.align(alignment_input, attempt_count=task.attempt_count)

    def _failure_outcome(
        self,
        alignment_input: EntityAlignmentInput,
        *,
        attempt_count: int | None,
    ) -> EntityAlignmentOutcome:
        log_kwargs: dict[str, str | int] = {
            "task_id": alignment_input.task_id,
            "archive_id": alignment_input.archive_id,
            "user_id": alignment_input.user_id,
            "failed_stage": "entity_alignment",
        }
        if attempt_count is not None:
            log_kwargs["attempt_count"] = attempt_count
        _logger.warning("entity alignment failed", **log_kwargs)
        return EntityAlignmentOutcome(
            outcome=EntityAlignmentOutcomeKind.FAILURE,
            success=None,
            failure=EntityAlignmentFailure(),
        )

    async def _align_entities(self, alignment_input: EntityAlignmentInput) -> list[AlignedEntity]:
        user_entity_id = build_user_entity_id(alignment_input.user_id)
        need_user_alignment = (
            RESERVED_USER_ENTITY_ID in alignment_input.referenced_local_entity_ids
            or any(
                entity.local_entity_id == RESERVED_USER_ENTITY_ID
                for entity in alignment_input.entities
            )
        )

        alignments: list[AlignedEntity] = []
        if need_user_alignment:
            alignments.append(await self._align_reserved_user(alignment_input.user_id))

        non_user_entities = [
            entity
            for entity in alignment_input.entities
            if entity.local_entity_id != RESERVED_USER_ENTITY_ID
        ]
        prepared = [
            (
                entity,
                normalize_entity_name(entity.name),
                compute_entity_key(
                    user_id=alignment_input.user_id,
                    entity_type=entity.type,
                    normalized_name=normalize_entity_name(entity.name),
                ),
            )
            for entity in non_user_entities
        ]

        entity_keys = [item[2] for item in prepared]
        entity_key_hits: dict[str, EntityNodeSnapshot] = {}
        if entity_keys:
            entity_key_hits = await self._repository.find_by_entity_keys(
                alignment_input.user_id,
                entity_keys,
            )

        secondary_candidates: list[SecondaryMatchCandidate] = []
        for entity, normalized_name, entity_key in prepared:
            if entity_key not in entity_key_hits:
                secondary_candidates.append(
                    SecondaryMatchCandidate(
                        local_entity_id=entity.local_entity_id,
                        entity_type=entity.type,
                        normalized_name=normalized_name,
                    )
                )
        secondary_rows: dict[str, list[EntityNodeSnapshot]] = {}
        if secondary_candidates:
            secondary_rows = await self._repository.find_secondary_match_candidates(
                alignment_input.user_id,
                secondary_candidates,
            )

        planned_entity_id_by_entity_key: dict[str, str] = {}
        for entity, normalized_name, entity_key in prepared:
            if entity_key in entity_key_hits:
                snapshot = entity_key_hits[entity_key]
                if snapshot.entity_id == user_entity_id:
                    raise EntityGraphDataError("non-user candidate matched reserved user entity")
                alignments.append(
                    self._aligned_existing(
                        entity=entity,
                        snapshot=snapshot,
                        match_kind=EntityMatchKind.ENTITY_KEY_EXACT,
                        normalized_name=normalized_name,
                        entity_key=entity_key,
                    )
                )
                continue

            candidate_rows = secondary_rows.get(entity.local_entity_id, [])
            hits = _secondary_hits(candidate_rows, normalized_name)
            if hits:
                snapshot = min(hits, key=lambda item: item.entity_id)
                if snapshot.entity_id == user_entity_id:
                    raise EntityGraphDataError("non-user candidate matched reserved user entity")
                alignments.append(
                    self._aligned_existing(
                        entity=entity,
                        snapshot=snapshot,
                        match_kind=EntityMatchKind.CANONICAL_OR_ALIAS_EXACT,
                        normalized_name=normalized_name,
                        entity_key=snapshot.entity_key,
                    )
                )
                continue

            entity_id = planned_entity_id_by_entity_key.get(entity_key)
            if entity_id is None:
                entity_id = self._entity_id_factory()
                planned_entity_id_by_entity_key[entity_key] = entity_id
            alignments.append(
                self._aligned_planned_create(
                    entity=entity,
                    entity_id=entity_id,
                    normalized_name=normalized_name,
                    entity_key=entity_key,
                )
            )

        return alignments

    async def _align_reserved_user(self, user_id: str) -> AlignedEntity:
        user_fields = planned_user_entity_fields(user_id)
        snapshot = await self._repository.find_user_entity(
            user_id,
            user_entity_id=user_fields["entity_id"],
        )
        if snapshot is not None:
            return AlignedEntity(
                local_entity_id=RESERVED_USER_ENTITY_ID,
                entity_id=snapshot.entity_id,
                match_kind=EntityMatchKind.RESERVED_USER_EXISTING,
                entity_type=snapshot.entity_type,
                canonical_name=snapshot.canonical_name,
                normalized_name=snapshot.normalized_name,
                entity_key=snapshot.entity_key,
                planned_alias_merge=PlannedEntityAliasMerge(
                    normalized_candidate_aliases=[],
                    existing_aliases=list(snapshot.aliases),
                    planned_aliases=list(snapshot.aliases),
                    omitted_alias_count=0,
                ),
                existing_entity=snapshot,
                planned_create=False,
            )

        return AlignedEntity(
            local_entity_id=RESERVED_USER_ENTITY_ID,
            entity_id=user_fields["entity_id"],
            match_kind=EntityMatchKind.RESERVED_USER_PLANNED_CREATE,
            entity_type=user_fields["entity_type"],
            canonical_name=user_fields["canonical_name"],
            normalized_name=user_fields["normalized_name"],
            entity_key=user_fields["entity_key"],
            planned_alias_merge=PlannedEntityAliasMerge(
                normalized_candidate_aliases=[],
                existing_aliases=[],
                planned_aliases=[],
                omitted_alias_count=0,
            ),
            existing_entity=None,
            planned_create=True,
        )

    def _aligned_existing(
        self,
        *,
        entity: ExtractionEntityCandidate,
        snapshot: EntityNodeSnapshot,
        match_kind: EntityMatchKind,
        normalized_name: str,
        entity_key: str,
    ) -> AlignedEntity:
        if snapshot.entity_type != entity.type:
            raise EntityGraphDataError("matched entity_type mismatch")
        return AlignedEntity(
            local_entity_id=entity.local_entity_id,
            entity_id=snapshot.entity_id,
            match_kind=match_kind,
            entity_type=entity.type,
            canonical_name=snapshot.canonical_name,
            normalized_name=snapshot.normalized_name,
            entity_key=entity_key,
            planned_alias_merge=_plan_alias_merge(
                existing_aliases=snapshot.aliases,
                candidate_aliases=entity.aliases,
                max_stored_entity_alias_count=self._max_stored_entity_alias_count,
            ),
            existing_entity=snapshot,
            planned_create=False,
        )

    def _aligned_planned_create(
        self,
        *,
        entity: ExtractionEntityCandidate,
        entity_id: str,
        normalized_name: str,
        entity_key: str,
    ) -> AlignedEntity:
        return AlignedEntity(
            local_entity_id=entity.local_entity_id,
            entity_id=entity_id,
            match_kind=EntityMatchKind.PLANNED_CREATE,
            entity_type=entity.type,
            canonical_name=entity.name,
            normalized_name=normalized_name,
            entity_key=entity_key,
            planned_alias_merge=_plan_alias_merge(
                existing_aliases=[],
                candidate_aliases=entity.aliases,
                max_stored_entity_alias_count=self._max_stored_entity_alias_count,
            ),
            existing_entity=None,
            planned_create=True,
        )


def create_entity_alignment_service(
    driver: Any,
    *,
    max_stored_entity_alias_count: int = 50,
    entity_id_factory: EntityIdFactory | None = None,
) -> EntityAlignmentService:
    repository = EntityAlignmentRepository(driver)
    return EntityAlignmentService(
        repository,
        max_stored_entity_alias_count=max_stored_entity_alias_count,
        entity_id_factory=entity_id_factory,
    )
