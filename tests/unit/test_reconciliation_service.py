"""Unit tests for reconciliation service (EXT-005)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

import pytest

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
from memory_system.domain.models.memory_recall import MemoryNodeSnapshot
from memory_system.domain.models.reconciliation import (
    ReasonCode,
    ReconciliationAbort,
    ReconciliationAction,
    ReconciliationErrorCode,
    ReconciliationInput,
    ReconciliationOutcomeKind,
)
from memory_system.domain.services.reconciliation_service import (
    ReconciliationService,
    build_aligned_candidate_views,
)
from memory_system.infrastructure.llm import FakeLlmClient
from memory_system.infrastructure.neo4j.memory_recall_repository import MemoryRecallKey
from memory_system.settings import get_settings


@dataclass
class FakeEvidenceRepository:
    processed: set[str] = field(default_factory=set)
    fail: bool = False
    calls: int = 0

    async def find_processed_evidence_ids(
        self, user_id: str, evidence_ids: list[str]
    ) -> set[str]:
        self.calls += 1
        if self.fail:
            raise RuntimeError("neo4j unavailable")
        return {item for item in evidence_ids if item in self.processed}


@dataclass
class FakeMemoryRecallRepository:
    recalls: dict[int, list[MemoryNodeSnapshot]] = field(default_factory=dict)
    fail: bool = False
    calls: int = 0

    async def recall_memories_batch(
        self,
        user_id: str,
        recall_keys: list[MemoryRecallKey],
    ) -> dict[int, list[MemoryNodeSnapshot]]:
        self.calls += 1
        if self.fail:
            raise RuntimeError("neo4j unavailable")
        return {
            key.candidate_index: self.recalls.get(key.candidate_index, [])
            for key in recall_keys
        }


def _memory(**overrides: Any) -> MemoryNodeSnapshot:
    base = {
        "memory_id": "mem-1",
        "user_id": "user-1",
        "memory_type": "fact",
        "content": "existing content",
        "subject_entity_id": "user:user-1",
        "predicate": "likes",
        "object_entity_id": None,
        "object_value": "tea",
        "status": "active",
        "event_status": None,
        "start_time": None,
        "end_time": None,
        "original_time_text": None,
        "confidence": 0.8,
        "latest_source_time": 100,
    }
    base.update(overrides)
    return MemoryNodeSnapshot(**base)


def _memory_candidate(**overrides: Any) -> ExtractionMemoryCandidate:
    base = {
        "memory_type": "fact",
        "content": "candidate content",
        "subject_entity_id": "user",
        "predicate": "likes",
        "object_entity_id": None,
        "object_value": "tea",
        "event_status": None,
        "start_time": None,
        "end_time": None,
        "original_time_text": None,
        "confidence": 0.9,
        "source_message_ids": ["msg_1"],
        "candidate_source_time": 200,
        "candidate_fingerprint": "fp-1",
    }
    base.update(overrides)
    return ExtractionMemoryCandidate(**base)


def _alignment(user_id: str = "user-1") -> EntityAlignmentSuccess:
    return EntityAlignmentSuccess(
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
            )
        ],
    )


def _input(
    *,
    memories: list[ExtractionMemoryCandidate] | None = None,
    alignment: EntityAlignmentSuccess | None = None,
) -> ReconciliationInput:
    validated = ExtractionValidatedResult(
        entities=[
            ExtractionEntityCandidate(
                local_entity_id="user",
                name="current_user",
                type="person",
                aliases=[],
            )
        ],
        memories=memories or [_memory_candidate()],
    )
    return ReconciliationInput(
        task_id="task-1",
        archive_id="archive-1",
        user_id="user-1",
        session_id="session-1",
        extraction_result=validated,
        entity_alignment=alignment or _alignment(),
    )


def _service(
    *,
    evidence: FakeEvidenceRepository | None = None,
    recall: FakeMemoryRecallRepository | None = None,
    llm: FakeLlmClient | None = None,
) -> ReconciliationService:
    return ReconciliationService(
        evidence or FakeEvidenceRepository(),
        recall or FakeMemoryRecallRepository(),
        llm_client=llm or FakeLlmClient(),
        settings=get_settings(),
        memory_id_factory=lambda: "planned-memory-id",
    )


@pytest.mark.asyncio
async def test_r1_zero_recall_deterministic_create_no_llm() -> None:
    llm = FakeLlmClient()
    service = _service(recall=FakeMemoryRecallRepository(), llm=llm)
    result = await service.reconcile(_input())
    assert not isinstance(result, ReconciliationAbort)
    assert result.outcome == ReconciliationOutcomeKind.SUCCESS
    assert result.success is not None
    assert result.success.per_candidate_decisions[0].action == ReconciliationAction.CREATE
    assert result.success.per_candidate_decisions[0].reason_code == ReasonCode.NEW_MEMORY
    assert llm.call_count == 0


@pytest.mark.asyncio
async def test_r2_merge_with_llm() -> None:
    llm = FakeLlmClient(
        success_content=(
            '{"action":"MERGE","target_memory_id":"mem-1",'
            '"reason_code":"same_semantic_memory","merged_content":null}'
        )
    )
    recall = FakeMemoryRecallRepository(recalls={0: [_memory()]})
    service = _service(recall=recall, llm=llm)
    result = await service.reconcile(_input())
    assert result.success is not None
    assert llm.call_count == 1
    assert result.success.existing_memory_update_plans[0].aggregated_action == "MERGE"


@pytest.mark.asyncio
async def test_r3_evidence_already_processed_skip() -> None:
    from memory_system.domain.services.evidence_identity import compute_evidence_id

    evidence_id = compute_evidence_id("archive-1", "fp-1")
    llm = FakeLlmClient()
    service = _service(evidence=FakeEvidenceRepository(processed={evidence_id}), llm=llm)
    result = await service.reconcile(_input())
    decision = result.success.per_candidate_decisions[0]  # type: ignore[union-attr]
    assert decision.action == ReconciliationAction.SKIP
    assert decision.skip_reason == "evidence_already_processed"
    assert decision.reason_code is None
    assert llm.call_count == 0


@pytest.mark.asyncio
async def test_r5_graph_query_failure() -> None:
    service = _service(evidence=FakeEvidenceRepository(fail=True))
    result = await service.reconcile(_input())
    assert result.failure is not None
    assert result.failure.error_code == ReconciliationErrorCode.GRAPH_QUERY_FAILED
    assert result.failure.failed_stage == "reconciliation"


@pytest.mark.asyncio
async def test_r6_plan_conflict() -> None:
    merge_response = (
        '{"action":"MERGE","target_memory_id":"mem-1",'
        '"reason_code":"same_semantic_memory","merged_content":"candidate content"}'
    )
    existing_response = (
        '{"action":"MERGE","target_memory_id":"mem-1",'
        '"reason_code":"same_semantic_memory","merged_content":"existing content"}'
    )
    llm = FakeLlmClient(responses=[merge_response, existing_response])
    recall = FakeMemoryRecallRepository(recalls={0: [_memory()], 1: [_memory()]})
    service = _service(recall=recall, llm=llm)
    result = await service.reconcile(
        _input(
            memories=[
                _memory_candidate(candidate_fingerprint="fp-1"),
                _memory_candidate(candidate_fingerprint="fp-2"),
            ]
        )
    )
    assert result.failure is not None
    assert result.failure.error_code == ReconciliationErrorCode.RECONCILIATION_PLAN_CONFLICT


@pytest.mark.asyncio
async def test_r7_llm_failure_codes_only() -> None:
    for mode, expected in (
        ("timeout", ReconciliationErrorCode.LLM_TIMEOUT),
        ("provider_error", ReconciliationErrorCode.LLM_REQUEST_FAILED),
    ):
        llm = FakeLlmClient(mode=mode)
        service = _service(recall=FakeMemoryRecallRepository(recalls={0: [_memory()]}), llm=llm)
        result = await service.reconcile(_input())
        assert result.failure is not None
        assert result.failure.error_code == expected


@pytest.mark.asyncio
async def test_r8_forbidden_error_codes_absent() -> None:
    service = _service(evidence=FakeEvidenceRepository(fail=True))
    result = await service.reconcile(_input())
    assert result.failure is not None
    assert result.failure.error_code.value not in {
        "entity_alignment_failed",
        "graph_write_failed",
        "archive_not_found",
    }


@pytest.mark.asyncio
async def test_r11_does_not_recompute_fingerprint() -> None:
    service = _service()
    with patch(
        "memory_system.domain.services.extraction_fingerprint.compute_candidate_fingerprint",
        side_effect=AssertionError("must not recompute fingerprint"),
    ):
        await service.reconcile(_input())


@pytest.mark.asyncio
async def test_r12_recall_batch_uses_user_scoped_repository() -> None:
    recall = FakeMemoryRecallRepository()
    service = _service(recall=recall)
    await service.reconcile(_input())
    assert recall.calls == 1


@pytest.mark.asyncio
async def test_r13_privacy_no_sensitive_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    service = _service(evidence=FakeEvidenceRepository(fail=True))
    await service.reconcile(_input())
    joined = " ".join(record.message for record in caplog.records)
    assert "candidate content" not in joined
    assert "merged_content" not in joined


@pytest.mark.asyncio
async def test_r14_abort_without_terminal_on_bad_alignment_map() -> None:
    service = _service()
    reconciliation_input = _input(
        memories=[_memory_candidate(subject_entity_id="missing-local-id")]
    )
    result = await service.reconcile(reconciliation_input)
    assert isinstance(result, ReconciliationAbort)


@pytest.mark.asyncio
async def test_r15_batch_recall_constant_query_count() -> None:
    recall = FakeMemoryRecallRepository()
    service = _service(recall=recall)
    memories = [
        _memory_candidate(candidate_fingerprint=f"fp-{index}") for index in range(50)
    ]
    await service.reconcile(_input(memories=memories))
    assert recall.calls == 1


def test_build_aligned_views_maps_user_entity() -> None:
    views = build_aligned_candidate_views(
        memories=[_memory_candidate()],
        archive_id="archive-1",
        local_entity_id_map={"user": "user:user-1"},
    )
    assert views[0].subject_entity_id == "user:user-1"
