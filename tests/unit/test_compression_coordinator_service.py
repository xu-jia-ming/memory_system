"""Unit tests for compression coordinator domain service (STM-009)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from memory_system.domain.enums.compression_coordinator import CompressionStatus
from memory_system.domain.enums.compression_finalize import CompressionFinalizeStatus
from memory_system.domain.enums.compression_preparation import CompressionPreparationStatus
from memory_system.domain.enums.context_read import ContextReadStatus
from memory_system.domain.enums.message_write import MessageWriteStatus
from memory_system.domain.enums.working_memory import MessageRole
from memory_system.domain.models.compression_finalize import CompressionFinalizeResult
from memory_system.domain.models.compression_llm import (
    CompressionLlmFailure,
    CompressionLlmOutcome,
    CompressionLlmResult,
    CompressionLlmSuccess,
)
from memory_system.domain.models.compression_preparation import CompressionPreparationResult
from memory_system.domain.models.context_read import ContextReadResult, WorkingMemorySnapshot
from memory_system.domain.models.message_write import MessageWriteInput, MessageWriteResult
from memory_system.domain.models.working_memory import WorkingMemoryMessage, WorkingMemoryMeta
from memory_system.domain.services.compression_coordinator_service import (
    InvalidMessageTimestampError,
    SessionNotFoundCoordinatorError,
    WorkingMemoryFullCoordinatorError,
    run_compression_coordination,
    select_archive_prefix,
    write_working_message_with_coordination,
)
from memory_system.infrastructure.llm import FakeLlmClient
from memory_system.settings import get_settings

USER_ID = "user_001"
SESSION_ID = "session_001"
MESSAGE_ID = "msg-001"
FIXED_NOW = 1_700_000_000


def _message(mid: str, tokens: int) -> WorkingMemoryMessage:
    return WorkingMemoryMessage(
        message_id=mid,
        role=MessageRole.USER,
        content="x" * max(tokens * 4, 1),
        estimated_tokens=tokens,
        timestamp=FIXED_NOW,
    )


def _write_input(**overrides: object) -> MessageWriteInput:
    data: dict[str, object] = {
        "user_id": USER_ID,
        "session_id": SESSION_ID,
        "message_id": MESSAGE_ID,
        "role": MessageRole.USER,
        "content": "hello world",
    }
    data.update(overrides)
    return MessageWriteInput.model_validate(data)


def _meta(*, estimated_tokens: int, pending_id: str | None = None) -> WorkingMemoryMeta:
    return WorkingMemoryMeta(
        user_id=USER_ID,
        session_id=SESSION_ID,
        estimated_tokens=estimated_tokens,
        created_time=FIXED_NOW,
        updated_time=FIXED_NOW,
        pending_archive_id=pending_id,
        pending_archive_batch_key="s:a:b" if pending_id else None,
        pending_archive_message_count=2 if pending_id else 0,
        pending_archive_estimated_tokens=100 if pending_id else 0,
    )


def _snapshot(messages: list[WorkingMemoryMessage]) -> WorkingMemorySnapshot:
    return WorkingMemorySnapshot(
        compression_version=0,
        compressed_context="",
        messages=messages,
    )


@pytest.fixture
def settings() -> Any:
    return get_settings()


@pytest.fixture
def llm_client() -> FakeLlmClient:
    return FakeLlmClient()


def test_select_archive_prefix_cap_shrink_from_tail() -> None:
    context = get_settings().context.model_copy(
        update={
            "preferred_recent_messages": 2,
            "absolute_min_recent_messages": 2,
            "max_archive_estimated_tokens": 150,
            "compression_target_tokens": 500,
        }
    )
    messages = [_message("m1", 100), _message("m2", 100), _message("m3", 50), _message("m4", 50)]
    selection = select_archive_prefix(
        messages=messages,
        meta_estimated_tokens=400,
        context=context,
    )
    assert selection is not None
    assert sum(m.estimated_tokens for m in selection.prefix) <= 150
    assert len(messages) - len(selection.prefix) >= context.absolute_min_recent_messages


def test_select_archive_prefix_insufficient_messages() -> None:
    context = get_settings().context
    messages = [_message("m1", 10), _message("m2", 10)]
    assert (
        select_archive_prefix(
            messages=messages,
            meta_estimated_tokens=100,
            context=context,
        )
        is None
    )


@pytest.mark.asyncio
async def test_u1_below_trigger_not_triggered(settings: Any, llm_client: FakeLlmClient) -> None:
    with patch(
        "memory_system.domain.services.compression_coordinator_service.write_message",
        new_callable=AsyncMock,
        return_value=MessageWriteResult(
            status=MessageWriteStatus.SUCCESS,
            message_id=MESSAGE_ID,
            estimated_tokens=100,
        ),
    ) as mock_write:
        result = await write_working_message_with_coordination(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            llm_client=llm_client,
            settings=settings,
            input=_write_input(),
            clock=lambda: FIXED_NOW,
        )
    assert result.compression_status == CompressionStatus.NOT_TRIGGERED
    assert result.status == "success"
    mock_write.assert_awaited_once()


@pytest.mark.asyncio
async def test_u2_trigger_single_round_completed(settings: Any, llm_client: FakeLlmClient) -> None:
    trigger = settings.context.compression_trigger_tokens
    with (
        patch(
            "memory_system.domain.services.compression_coordinator_service.write_message",
            new_callable=AsyncMock,
            return_value=MessageWriteResult(
                status=MessageWriteStatus.SUCCESS,
                message_id=MESSAGE_ID,
                estimated_tokens=trigger,
            ),
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service.run_compression_coordination",
            new_callable=AsyncMock,
            return_value=MagicMock(
                status=CompressionStatus.COMPLETED,
                rounds_completed=1,
            ),
        ) as mock_coord,
    ):
        result = await write_working_message_with_coordination(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            llm_client=llm_client,
            settings=settings,
            input=_write_input(),
        )
    assert result.compression_status == CompressionStatus.COMPLETED
    mock_coord.assert_awaited_once()


@pytest.mark.asyncio
async def test_u3_duplicate_not_triggered(settings: Any, llm_client: FakeLlmClient) -> None:
    with patch(
        "memory_system.domain.services.compression_coordinator_service.write_message",
        new_callable=AsyncMock,
        return_value=MessageWriteResult(
            status=MessageWriteStatus.DUPLICATE,
            message_id=MESSAGE_ID,
        ),
    ):
        result = await write_working_message_with_coordination(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            llm_client=llm_client,
            settings=settings,
            input=_write_input(),
        )
    assert result.status == "duplicate"
    assert result.compression_status == CompressionStatus.NOT_TRIGGERED


@pytest.mark.asyncio
async def test_u4_message_too_large(settings: Any, llm_client: FakeLlmClient) -> None:
    with patch(
        "memory_system.domain.services.compression_coordinator_service.write_message",
        new_callable=AsyncMock,
        return_value=MessageWriteResult(
            status=MessageWriteStatus.MESSAGE_TOO_LARGE,
            message_id=MESSAGE_ID,
        ),
    ):
        with pytest.raises(Exception) as exc_info:
            await write_working_message_with_coordination(
                redis=MagicMock(),
                mongodb=MagicMock(),
                kafka_producer=MagicMock(),
                llm_client=llm_client,
                settings=settings,
                input=_write_input(),
            )
    assert exc_info.type.__name__ == "MessageTooLargeCoordinatorError"


@pytest.mark.asyncio
async def test_u5_capacity_compression_then_retry_success(
    settings: Any,
    llm_client: FakeLlmClient,
) -> None:
    trigger = settings.context.compression_trigger_tokens
    with (
        patch(
            "memory_system.domain.services.compression_coordinator_service.write_message",
            new_callable=AsyncMock,
            side_effect=[
                MessageWriteResult(
                    status=MessageWriteStatus.CAPACITY_EXCEEDED,
                    message_id=MESSAGE_ID,
                ),
                MessageWriteResult(
                    status=MessageWriteStatus.SUCCESS,
                    message_id=MESSAGE_ID,
                    estimated_tokens=trigger,
                ),
            ],
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service.run_compression_coordination",
            new_callable=AsyncMock,
            return_value=MagicMock(
                status=CompressionStatus.COMPLETED,
                rounds_completed=1,
            ),
        ) as mock_coord,
    ):
        result = await write_working_message_with_coordination(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            llm_client=llm_client,
            settings=settings,
            input=_write_input(),
        )
    assert result.status == "success"
    mock_coord.assert_awaited()


@pytest.mark.asyncio
async def test_u6_capacity_retry_still_full(settings: Any, llm_client: FakeLlmClient) -> None:
    with (
        patch(
            "memory_system.domain.services.compression_coordinator_service.write_message",
            new_callable=AsyncMock,
            side_effect=[
                MessageWriteResult(
                    status=MessageWriteStatus.CAPACITY_EXCEEDED,
                    message_id=MESSAGE_ID,
                ),
                MessageWriteResult(
                    status=MessageWriteStatus.CAPACITY_EXCEEDED,
                    message_id=MESSAGE_ID,
                ),
            ],
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service.run_compression_coordination",
            new_callable=AsyncMock,
        ),
    ):
        with pytest.raises(WorkingMemoryFullCoordinatorError):
            await write_working_message_with_coordination(
                redis=MagicMock(),
                mongodb=MagicMock(),
                kafka_producer=MagicMock(),
                llm_client=llm_client,
                settings=settings,
                input=_write_input(),
            )


@pytest.mark.asyncio
async def test_u7_session_not_found_pre_write(settings: Any, llm_client: FakeLlmClient) -> None:
    with patch(
        "memory_system.domain.services.compression_coordinator_service.write_message",
        new_callable=AsyncMock,
        return_value=MessageWriteResult(
            status=MessageWriteStatus.SESSION_NOT_FOUND,
            message_id=MESSAGE_ID,
        ),
    ):
        with pytest.raises(SessionNotFoundCoordinatorError):
            await write_working_message_with_coordination(
                redis=MagicMock(),
                mongodb=MagicMock(),
                kafka_producer=MagicMock(),
                llm_client=llm_client,
                settings=settings,
                input=_write_input(),
            )


@pytest.mark.asyncio
async def test_u10_lock_not_acquired_skipped_lock(settings: Any, llm_client: FakeLlmClient) -> None:
    trigger = settings.context.compression_trigger_tokens
    with (
        patch(
            "memory_system.domain.services.compression_coordinator_service.get_working_memory_meta",
            new_callable=AsyncMock,
            return_value=_meta(estimated_tokens=trigger),
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service._run_single_compression_round",
            new_callable=AsyncMock,
            return_value=CompressionStatus.SKIPPED_LOCK,
        ),
    ):
        result = await run_compression_coordination(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            llm_client=llm_client,
            settings=settings,
            user_id=USER_ID,
            session_id=SESSION_ID,
        )
    assert result.status == CompressionStatus.SKIPPED_LOCK


@pytest.mark.asyncio
async def test_u12_kafka_publish_failed_continues_to_llm(
    settings: Any,
    llm_client: FakeLlmClient,
) -> None:
    trigger = settings.context.compression_trigger_tokens
    messages = [_message(f"m{i}", 50) for i in range(5)]
    stage_log: list[str] = []
    with (
        patch(
            "memory_system.domain.services.compression_coordinator_service.get_working_memory_meta",
            new_callable=AsyncMock,
            side_effect=[
                _meta(estimated_tokens=trigger),
                _meta(estimated_tokens=trigger),
                _meta(estimated_tokens=100),
            ],
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service.read_working_memory_context",
            new_callable=AsyncMock,
            return_value=ContextReadResult(
                status=ContextReadStatus.SUCCESS,
                snapshot=_snapshot(messages),
            ),
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service.create_or_reuse_context_archive",
            new_callable=AsyncMock,
            return_value=MagicMock(archive_id="arch-1"),
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service.prepare_pending_archive_and_publish",
            new_callable=AsyncMock,
            return_value=CompressionPreparationResult(
                status=CompressionPreparationStatus.PUBLISH_FAILED,
                lock_owner_token="tok",
                event_id=None,
            ),
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service.run_compression_llm",
            new_callable=AsyncMock,
            return_value=CompressionLlmResult(
                outcome=CompressionLlmOutcome.SUCCESS,
                success=CompressionLlmSuccess(
                    compressed_context="c",
                    new_compressed_context_tokens=1,
                    prompt_version="v1",
                    model="fake",
                ),
            ),
        ) as mock_llm,
        patch(
            "memory_system.domain.services.compression_coordinator_service.finalize_compression",
            new_callable=AsyncMock,
            return_value=CompressionFinalizeResult(
                status=CompressionFinalizeStatus.SUCCESS,
                new_compression_version=1,
                new_estimated_tokens=100,
            ),
        ),
    ):
        result = await run_compression_coordination(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            llm_client=llm_client,
            settings=settings,
            user_id=USER_ID,
            session_id=SESSION_ID,
            stage_log=stage_log,
        )
    assert result.status == CompressionStatus.COMPLETED
    mock_llm.assert_awaited_once()


@pytest.mark.asyncio
async def test_u14_llm_timeout_failed_no_finalize(settings: Any, llm_client: FakeLlmClient) -> None:
    trigger = settings.context.compression_trigger_tokens
    messages = [_message(f"m{i}", 500) for i in range(5)]
    with (
        patch(
            "memory_system.domain.services.compression_coordinator_service.get_working_memory_meta",
            new_callable=AsyncMock,
            return_value=_meta(estimated_tokens=trigger),
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service.read_working_memory_context",
            new_callable=AsyncMock,
            return_value=ContextReadResult(
                status=ContextReadStatus.SUCCESS,
                snapshot=_snapshot(messages),
            ),
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service.create_or_reuse_context_archive",
            new_callable=AsyncMock,
            return_value=MagicMock(archive_id="arch-1"),
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service.prepare_pending_archive_and_publish",
            new_callable=AsyncMock,
            return_value=CompressionPreparationResult(
                status=CompressionPreparationStatus.SUCCESS,
                lock_owner_token="tok",
                event_id="e1",
            ),
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service.run_compression_llm",
            new_callable=AsyncMock,
            return_value=CompressionLlmResult(
                outcome=CompressionLlmOutcome.FAILURE,
                failure=CompressionLlmFailure(
                    error_code="llm_timeout",
                    prompt_version="v1",
                    model="fake",
                    attempt_count=1,
                ),
            ),
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service.finalize_compression",
            new_callable=AsyncMock,
        ) as mock_finalize,
    ):
        result = await run_compression_coordination(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            llm_client=llm_client,
            settings=settings,
            user_id=USER_ID,
            session_id=SESSION_ID,
        )
    assert result.status == CompressionStatus.FAILED
    mock_finalize.assert_not_awaited()


@pytest.mark.asyncio
async def test_u17_finalize_version_conflict(settings: Any, llm_client: FakeLlmClient) -> None:
    trigger = settings.context.compression_trigger_tokens
    with (
        patch(
            "memory_system.domain.services.compression_coordinator_service.get_working_memory_meta",
            new_callable=AsyncMock,
            return_value=_meta(estimated_tokens=trigger),
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service._run_single_compression_round",
            new_callable=AsyncMock,
            return_value=CompressionStatus.VERSION_CONFLICT,
        ),
    ):
        result = await run_compression_coordination(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            llm_client=llm_client,
            settings=settings,
            user_id=USER_ID,
            session_id=SESSION_ID,
        )
    assert result.status == CompressionStatus.VERSION_CONFLICT


@pytest.mark.asyncio
async def test_u19_stage_ordering_archive_pending_llm_finalize(
    settings: Any,
    llm_client: FakeLlmClient,
) -> None:
    trigger = settings.context.compression_trigger_tokens
    messages = [_message(f"m{i}", 50) for i in range(5)]
    stage_log: list[str] = []
    with (
        patch(
            "memory_system.domain.services.compression_coordinator_service.get_working_memory_meta",
            new_callable=AsyncMock,
            side_effect=[
                _meta(estimated_tokens=trigger),
                _meta(estimated_tokens=trigger),
                _meta(estimated_tokens=100),
            ],
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service.read_working_memory_context",
            new_callable=AsyncMock,
            return_value=ContextReadResult(
                status=ContextReadStatus.SUCCESS,
                snapshot=_snapshot(messages),
            ),
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service.create_or_reuse_context_archive",
            new_callable=AsyncMock,
            return_value=MagicMock(archive_id="arch-1"),
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service.prepare_pending_archive_and_publish",
            new_callable=AsyncMock,
            return_value=CompressionPreparationResult(
                status=CompressionPreparationStatus.SUCCESS,
                lock_owner_token="tok",
                event_id="e1",
            ),
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service.run_compression_llm",
            new_callable=AsyncMock,
            return_value=CompressionLlmResult(
                outcome=CompressionLlmOutcome.SUCCESS,
                success=CompressionLlmSuccess(
                    compressed_context="c",
                    new_compressed_context_tokens=1,
                    prompt_version="v1",
                    model="fake",
                ),
            ),
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service.finalize_compression",
            new_callable=AsyncMock,
            return_value=CompressionFinalizeResult(
                status=CompressionFinalizeStatus.SUCCESS,
                new_compression_version=1,
                new_estimated_tokens=100,
            ),
        ),
    ):
        await run_compression_coordination(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            llm_client=llm_client,
            settings=settings,
            user_id=USER_ID,
            session_id=SESSION_ID,
            stage_log=stage_log,
        )
    assert stage_log == ["archive", "pending", "llm", "finalize"]


@pytest.mark.asyncio
async def test_u20_multi_round_partial_completed(settings: Any, llm_client: FakeLlmClient) -> None:
    trigger = settings.context.compression_trigger_tokens
    small_settings = settings.model_copy(
        update={
            "context": settings.context.model_copy(
                update={"max_compression_rounds_per_request": 2}
            )
        }
    )
    high_meta = _meta(estimated_tokens=trigger)
    with (
        patch(
            "memory_system.domain.services.compression_coordinator_service.get_working_memory_meta",
            new_callable=AsyncMock,
            return_value=high_meta,
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service._run_single_compression_round",
            new_callable=AsyncMock,
            return_value=CompressionStatus.COMPLETED,
        ),
    ):
        result = await run_compression_coordination(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            llm_client=llm_client,
            settings=small_settings,
            user_id=USER_ID,
            session_id=SESSION_ID,
        )
    assert result.status == CompressionStatus.PARTIAL_COMPLETED
    assert result.rounds_completed == 2


@pytest.mark.asyncio
async def test_multi_round_partial_fail_prior_rounds_not_rolled_back(
    settings: Any,
    llm_client: FakeLlmClient,
) -> None:
    trigger = settings.context.compression_trigger_tokens
    high_meta = _meta(estimated_tokens=trigger)
    with (
        patch(
            "memory_system.domain.services.compression_coordinator_service.get_working_memory_meta",
            new_callable=AsyncMock,
            return_value=high_meta,
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service._run_single_compression_round",
            new_callable=AsyncMock,
            side_effect=[
                CompressionStatus.COMPLETED,
                CompressionStatus.FAILED,
            ],
        ),
    ):
        result = await run_compression_coordination(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            llm_client=llm_client,
            settings=settings,
            user_id=USER_ID,
            session_id=SESSION_ID,
        )
    assert result.status == CompressionStatus.FAILED
    assert result.rounds_completed == 1


@pytest.mark.asyncio
async def test_later_round_lock_fail_aggregates_failed(
    settings: Any,
    llm_client: FakeLlmClient,
) -> None:
    trigger = settings.context.compression_trigger_tokens
    high_meta = _meta(estimated_tokens=trigger)
    with (
        patch(
            "memory_system.domain.services.compression_coordinator_service.get_working_memory_meta",
            new_callable=AsyncMock,
            return_value=high_meta,
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service._run_single_compression_round",
            new_callable=AsyncMock,
            side_effect=[
                CompressionStatus.COMPLETED,
                CompressionStatus.SKIPPED_LOCK,
            ],
        ),
    ):
        result = await run_compression_coordination(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            llm_client=llm_client,
            settings=settings,
            user_id=USER_ID,
            session_id=SESSION_ID,
        )
    assert result.status == CompressionStatus.FAILED
    assert result.rounds_completed == 1


@pytest.mark.asyncio
async def test_invalid_message_timestamp(settings: Any, llm_client: FakeLlmClient) -> None:
    with pytest.raises(InvalidMessageTimestampError):
        await write_working_message_with_coordination(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            llm_client=llm_client,
            settings=settings,
            input=_write_input(timestamp=FIXED_NOW + 10_000),
            clock=lambda: FIXED_NOW,
        )


@pytest.mark.asyncio
async def test_u11_pending_conflict_failed(settings: Any, llm_client: FakeLlmClient) -> None:
    trigger = settings.context.compression_trigger_tokens
    with (
        patch(
            "memory_system.domain.services.compression_coordinator_service.get_working_memory_meta",
            new_callable=AsyncMock,
            return_value=_meta(estimated_tokens=trigger),
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service._run_single_compression_round",
            new_callable=AsyncMock,
            return_value=CompressionStatus.FAILED,
        ),
    ):
        result = await run_compression_coordination(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            llm_client=llm_client,
            settings=settings,
            user_id=USER_ID,
            session_id=SESSION_ID,
        )
    assert result.status == CompressionStatus.FAILED


@pytest.mark.asyncio
async def test_u8_archive_created_path_records_stage(
    settings: Any,
    llm_client: FakeLlmClient,
) -> None:
    trigger = settings.context.compression_trigger_tokens
    messages = [_message(f"m{i}", 50) for i in range(5)]
    stage_log: list[str] = []
    archive_mock = MagicMock(archive_id="new-arch")
    with (
        patch(
            "memory_system.domain.services.compression_coordinator_service.get_working_memory_meta",
            new_callable=AsyncMock,
            side_effect=[
                _meta(estimated_tokens=trigger),
                _meta(estimated_tokens=trigger),
                _meta(estimated_tokens=100),
            ],
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service.read_working_memory_context",
            new_callable=AsyncMock,
            return_value=ContextReadResult(
                status=ContextReadStatus.SUCCESS,
                snapshot=_snapshot(messages),
            ),
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service.create_or_reuse_context_archive",
            new_callable=AsyncMock,
            return_value=archive_mock,
        ) as mock_create,
        patch(
            "memory_system.domain.services.compression_coordinator_service.prepare_pending_archive_and_publish",
            new_callable=AsyncMock,
            return_value=CompressionPreparationResult(
                status=CompressionPreparationStatus.SUCCESS,
                lock_owner_token="tok",
                event_id="e1",
            ),
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service.run_compression_llm",
            new_callable=AsyncMock,
            return_value=CompressionLlmResult(
                outcome=CompressionLlmOutcome.SUCCESS,
                success=CompressionLlmSuccess(
                    compressed_context="c",
                    new_compressed_context_tokens=1,
                    prompt_version="v1",
                    model="fake",
                ),
            ),
        ),
        patch(
            "memory_system.domain.services.compression_coordinator_service.finalize_compression",
            new_callable=AsyncMock,
            return_value=CompressionFinalizeResult(
                status=CompressionFinalizeStatus.SUCCESS,
                new_compression_version=1,
                new_estimated_tokens=100,
            ),
        ),
    ):
        await run_compression_coordination(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            llm_client=llm_client,
            settings=settings,
            user_id=USER_ID,
            session_id=SESSION_ID,
            stage_log=stage_log,
        )
    mock_create.assert_awaited_once()
    assert "archive" in stage_log


def test_archive_selection_prefers_larger_prefix_within_target() -> None:
    context = get_settings().context.model_copy(
        update={
            "preferred_recent_messages": 3,
            "absolute_min_recent_messages": 2,
            "compression_target_tokens": 200,
            "max_archive_estimated_tokens": 5000,
        }
    )
    messages = [_message(f"m{i}", 100) for i in range(6)]
    selection = select_archive_prefix(
        messages=messages,
        meta_estimated_tokens=600,
        context=context,
    )
    assert selection is not None
    assert selection.projected_remaining <= context.compression_target_tokens
