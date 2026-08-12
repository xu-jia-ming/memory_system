"""Unit tests for graph_write_plan_builder (EXT-006)."""

from __future__ import annotations

from typing import Any

import pytest
from pymongo import AsyncMongoClient

from memory_system.domain.models.entity_alignment import (
    AlignedEntity,
    EntityAlignmentSuccess,
    EntityMatchKind,
    PlannedEntityAliasMerge,
)
from memory_system.domain.models.extraction_llm import (
    ExtractionEntityCandidate,
    ExtractionMemoryCandidate,
    ExtractionValidatedResult,
)
from memory_system.domain.models.graph_write import (
    GraphWriteInput,
    GraphWriteOutcomeKind,
    ImmutableGraphWritePlan,
)
from memory_system.domain.models.reconciliation import (
    PerCandidateDecision,
    PlannedExistingMemoryUpdate,
    PlannedMemoryCreate,
    ReasonCode,
    ReconciliationAction,
    ReconciliationSuccess,
)
from memory_system.domain.services.graph_write_plan_builder import build_graph_write_plan
from memory_system.infrastructure.tei.fake_tokenize_client import FakeTokenizeClient


class _FakeArchiveTimestampRepository:
    async def resolve_source_time_range(
        self,
        mongodb: AsyncMongoClient[Any],
        archive_id: str,
        source_message_ids: list[str],
        candidate_source_time: int,
    ) -> tuple[int, int]:
        if len(source_message_ids) == 1:
            return candidate_source_time, candidate_source_time
        timestamps = [100, 200]
        return min(timestamps), max(timestamps)


def _graph_input() -> GraphWriteInput:
    user_id = "user-1"
    return GraphWriteInput(
        task_id="task-1",
        archive_id="archive-1",
        user_id=user_id,
        session_id="session-1",
        extraction_result=ExtractionValidatedResult(
            entities=[
                ExtractionEntityCandidate(
                    local_entity_id="entity_1",
                    name="Agent Memory System",
                    type="project",
                    aliases=[],
                ),
            ],
            memories=[
                ExtractionMemoryCandidate(
                    memory_type="event",
                    content="content",
                    subject_entity_id="user",
                    predicate="works_on",
                    object_entity_id="entity_1",
                    object_value=None,
                    event_status="ongoing",
                    start_time=None,
                    end_time=None,
                    original_time_text=None,
                    confidence=0.9,
                    source_message_ids=["msg-1"],
                    candidate_source_time=150,
                    candidate_fingerprint="fp-1",
                ),
            ],
        ),
        entity_alignment=EntityAlignmentSuccess(
            user_id=user_id,
            alignments=[
                AlignedEntity(
                    local_entity_id="user",
                    entity_id=f"user:{user_id}",
                    match_kind=EntityMatchKind.RESERVED_USER_EXISTING,
                    entity_type="person",
                    canonical_name="current_user",
                    normalized_name="current_user",
                    entity_key="user-key",
                    planned_alias_merge=PlannedEntityAliasMerge(
                        normalized_candidate_aliases=[],
                        existing_aliases=[],
                        planned_aliases=[],
                        omitted_alias_count=0,
                    ),
                    existing_entity=None,
                    planned_create=False,
                ),
                AlignedEntity(
                    local_entity_id="entity_1",
                    entity_id="entity-uuid-1",
                    match_kind=EntityMatchKind.PLANNED_CREATE,
                    entity_type="project",
                    canonical_name="Agent Memory System",
                    normalized_name="agent memory system",
                    entity_key="entity-key-1",
                    planned_alias_merge=PlannedEntityAliasMerge(
                        normalized_candidate_aliases=[],
                        existing_aliases=[],
                        planned_aliases=[],
                        omitted_alias_count=0,
                    ),
                    existing_entity=None,
                    planned_create=True,
                ),
            ],
        ),
        reconciliation=ReconciliationSuccess(
            user_id=user_id,
            archive_id="archive-1",
            per_candidate_decisions=[
                PerCandidateDecision(
                    candidate_index=0,
                    candidate_fingerprint="fp-1",
                    evidence_id="ev-1",
                    action=ReconciliationAction.CREATE,
                    target_memory_id=None,
                    reason_code=ReasonCode.NEW_MEMORY,
                    skip_reason=None,
                    merged_content=None,
                    recalled_memory_count=0,
                    aligned_memory_key="key-1",
                ),
            ],
            existing_memory_update_plans=[
                PlannedExistingMemoryUpdate(
                    target_memory_id="mem-existing-1",
                    aggregated_action="MERGE",
                    contributing_candidate_indices=[0],
                    contributing_evidence_ids=["ev-1"],
                    planned_merged_content="merged content",
                    planned_merged_confidence=0.85,
                    planned_latest_source_time=150,
                    increment_memory_version=True,
                    planned_new_memory_id=None,
                ),
            ],
            new_memory_create_plans=[
                PlannedMemoryCreate(
                    create_kind="create",
                    planned_memory_id="mem-new-1",
                    aligned_memory_key="key-1",
                    supersedes_target_memory_id=None,
                    conflicts_with_target_memory_id=None,
                    memory_type="event",
                    planned_content="content",
                    subject_entity_id=f"user:{user_id}",
                    predicate="works_on",
                    object_entity_id="entity-uuid-1",
                    object_value=None,
                    event_status="ongoing",
                    start_time=None,
                    end_time=None,
                    original_time_text=None,
                    planned_confidence=0.9,
                    planned_importance=0.55,
                    planned_latest_source_time=150,
                    contributing_candidate_indices=[0],
                    contributing_evidence_ids=["ev-1"],
                ),
            ],
        ),
    )


@pytest.mark.asyncio
async def test_p1_token_count_within_limit_freezes_plan() -> None:
    result = await build_graph_write_plan(
        _graph_input(),
        mongodb=AsyncMongoClient("mongodb://localhost:27017/memory_system"),
        tokenize_client=FakeTokenizeClient(token_count=512),
        archive_timestamp_repository=_FakeArchiveTimestampRepository(),
        prompt_version="memory_extraction_v1",
        max_search_text_tokens=1024,
        server_time_provider=lambda: 1_700_000_000,
    )
    assert isinstance(result, ImmutableGraphWritePlan)
    assert result.memory_create_rows[0].memory_id == "mem-new-1"


@pytest.mark.asyncio
async def test_p2_token_count_over_limit_returns_failure() -> None:
    result = await build_graph_write_plan(
        _graph_input(),
        mongodb=AsyncMongoClient("mongodb://localhost:27017/memory_system"),
        tokenize_client=FakeTokenizeClient(token_count=2000),
        archive_timestamp_repository=_FakeArchiveTimestampRepository(),
        prompt_version="memory_extraction_v1",
        max_search_text_tokens=1024,
        server_time_provider=lambda: 1_700_000_000,
    )
    assert not isinstance(result, ImmutableGraphWritePlan)
    assert result.outcome == GraphWriteOutcomeKind.FAILURE
    assert result.failure is not None
    assert result.failure.error_code == "memory_search_text_too_long"


@pytest.mark.asyncio
async def test_p3_index_sync_covers_create_and_update_memory_ids() -> None:
    result = await build_graph_write_plan(
        _graph_input(),
        mongodb=AsyncMongoClient("mongodb://localhost:27017/memory_system"),
        tokenize_client=FakeTokenizeClient(token_count=10),
        archive_timestamp_repository=_FakeArchiveTimestampRepository(),
        prompt_version="memory_extraction_v1",
        max_search_text_tokens=1024,
        server_time_provider=lambda: 1_700_000_000,
    )
    assert isinstance(result, ImmutableGraphWritePlan)
    memory_ids = {entry.memory_id for entry in result.index_sync_memory_set}
    assert memory_ids == {"mem-new-1", "mem-existing-1"}
