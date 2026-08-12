"""Unit tests for reconciliation LLM service (EXT-005)."""

from __future__ import annotations

import json

import pytest

from memory_system.domain.models.memory_recall import MemoryNodeSnapshot
from memory_system.domain.models.reconciliation import (
    AlignedMemoryCandidateView,
    ReconciliationErrorCode,
    ReconciliationLlmOutput,
    ReconciliationOutcomeKind,
)
from memory_system.domain.services.reconciliation_llm_service import (
    FAILED_STAGE,
    RECONCILIATION_PROMPT_VERSION,
    run_reconciliation_llm,
)
from memory_system.infrastructure.llm import FakeLlmClient
from memory_system.settings import get_settings


def _candidate() -> AlignedMemoryCandidateView:
    return AlignedMemoryCandidateView(
        candidate_index=0,
        memory_type="fact",
        content="candidate content",
        predicate="likes",
        object_value="tea",
        event_status=None,
        start_time=None,
        end_time=None,
        original_time_text=None,
        confidence=0.9,
        source_message_ids=["msg_1"],
        candidate_source_time=200,
        candidate_fingerprint="fp-1",
        subject_entity_id="user:user-1",
        object_entity_id=None,
        evidence_id="ev-1",
    )


def _existing(memory_id: str = "mem-1", content: str = "existing content") -> MemoryNodeSnapshot:
    return MemoryNodeSnapshot(
        memory_id=memory_id,
        user_id="user-1",
        memory_type="fact",
        content=content,
        subject_entity_id="user:user-1",
        predicate="likes",
        object_entity_id=None,
        object_value="tea",
        status="active",
        event_status=None,
        start_time=None,
        end_time=None,
        original_time_text=None,
        confidence=0.8,
        latest_source_time=100,
    )


def _llm_json(**overrides: object) -> str:
    payload = {
        "action": "MERGE",
        "target_memory_id": "mem-1",
        "reason_code": "same_semantic_memory",
        "merged_content": None,
    }
    payload.update(overrides)
    return json.dumps(payload)


@pytest.mark.asyncio
async def test_l1_valid_structured_output() -> None:
    client = FakeLlmClient(responses=[_llm_json()])
    result = await run_reconciliation_llm(
        task_id="task-1",
        archive_id="archive-1",
        user_id="user-1",
        candidate=_candidate(),
        existing_memories=[_existing()],
        llm_client=client,
        settings=get_settings(),
    )
    assert isinstance(result, ReconciliationLlmOutput)
    assert result.action.value == "MERGE"


@pytest.mark.asyncio
async def test_l2_invalid_target_memory_id() -> None:
    client = FakeLlmClient(responses=[_llm_json(target_memory_id="missing")])
    result = await run_reconciliation_llm(
        task_id="task-1",
        archive_id="archive-1",
        user_id="user-1",
        candidate=_candidate(),
        existing_memories=[_existing()],
        llm_client=client,
        settings=get_settings(),
    )
    assert result.outcome == ReconciliationOutcomeKind.FAILURE
    assert result.failure is not None
    assert result.failure.error_code == ReconciliationErrorCode.LLM_INVALID_OUTPUT


@pytest.mark.asyncio
async def test_l3_additional_evidence_requires_merged_content() -> None:
    client = FakeLlmClient(
        responses=[
            _llm_json(
                reason_code="additional_evidence",
                merged_content=None,
            )
        ]
    )
    result = await run_reconciliation_llm(
        task_id="task-1",
        archive_id="archive-1",
        user_id="user-1",
        candidate=_candidate(),
        existing_memories=[_existing(content="different existing")],
        llm_client=client,
        settings=get_settings(),
    )
    assert result.failure is not None
    assert result.failure.error_code == ReconciliationErrorCode.LLM_INVALID_OUTPUT


@pytest.mark.asyncio
async def test_l4_merged_content_third_source_rejected() -> None:
    client = FakeLlmClient(
        responses=[
            _llm_json(
                reason_code="additional_evidence",
                merged_content="candidate content with alien phrase",
            )
        ]
    )
    result = await run_reconciliation_llm(
        task_id="task-1",
        archive_id="archive-1",
        user_id="user-1",
        candidate=_candidate(),
        existing_memories=[_existing(content="existing content")],
        llm_client=client,
        settings=get_settings(),
    )
    assert result.failure is not None
    assert result.failure.error_code == ReconciliationErrorCode.LLM_INVALID_OUTPUT


@pytest.mark.asyncio
async def test_l5_correction_retry_success() -> None:
    client = FakeLlmClient(
        responses=[
            "not-json",
            _llm_json(),
        ]
    )
    result = await run_reconciliation_llm(
        task_id="task-1",
        archive_id="archive-1",
        user_id="user-1",
        candidate=_candidate(),
        existing_memories=[_existing()],
        llm_client=client,
        settings=get_settings(),
    )
    assert client.call_count == 2
    assert result.action.value == "MERGE"


@pytest.mark.asyncio
async def test_l6_failed_stage_is_reconciliation() -> None:
    client = FakeLlmClient(mode="timeout")
    result = await run_reconciliation_llm(
        task_id="task-1",
        archive_id="archive-1",
        user_id="user-1",
        candidate=_candidate(),
        existing_memories=[_existing()],
        llm_client=client,
        settings=get_settings(),
    )
    assert result.failure is not None
    assert result.failure.failed_stage == FAILED_STAGE
    assert RECONCILIATION_PROMPT_VERSION == "memory_reconciliation_v1"
