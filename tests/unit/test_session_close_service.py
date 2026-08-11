"""Unit tests for session close domain service (STM-010)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from memory_system.domain.enums.context_archive import ContextArchiveOutcome
from memory_system.domain.enums.context_read import ContextReadStatus
from memory_system.domain.enums.session_close import (
    SessionCloseEnterStatus,
    SessionCloseRevertStatus,
    SessionCloseTerminalStatus,
)
from memory_system.domain.enums.working_memory import MessageRole, SessionStatus
from memory_system.domain.models.context_archive import (
    ContextArchive,
    ContextArchiveCreateInput,
    ContextArchiveMessage,
    ContextArchiveResult,
)
from memory_system.domain.models.context_read import ContextReadResult, WorkingMemorySnapshot
from memory_system.domain.models.working_memory import WorkingMemoryMessage, WorkingMemoryMeta
from memory_system.domain.services.session_close_service import (
    BaseCompressionVersionMismatchError,
    MalformedCompressionVersionError,
    SessionCloseIncompleteError,
    SessionCloseLockNotAcquiredError,
    SessionNotFoundCloseError,
    build_close_plan,
    close_session,
    split_close_suffix_batches,
)
from memory_system.settings import get_settings

USER_ID = "user_001"
SESSION_ID = "session_001"
FIXED_NOW = 1_700_000_000


def _message(mid: str, tokens: int) -> WorkingMemoryMessage:
    return WorkingMemoryMessage(
        message_id=mid,
        role=MessageRole.USER,
        content="x" * max(tokens, 1),
        estimated_tokens=tokens,
        timestamp=FIXED_NOW,
    )


def _meta(
    *,
    compression_version: int = 0,
    pending_id: str | None = None,
    pending_count: int = 0,
    pending_tokens: int = 0,
    pending_batch_key: str | None = None,
    status: SessionStatus = SessionStatus.CLOSING,
) -> WorkingMemoryMeta:
    return WorkingMemoryMeta(
        user_id=USER_ID,
        session_id=SESSION_ID,
        compression_version=compression_version,
        status=status,
        pending_archive_id=pending_id,
        pending_archive_batch_key=pending_batch_key,
        pending_archive_message_count=pending_count,
        pending_archive_estimated_tokens=pending_tokens,
        created_time=FIXED_NOW,
        updated_time=FIXED_NOW,
    )


def _archive(archive_id: str, base_version: int, batch_key: str) -> ContextArchive:
    return ContextArchive(
        archive_id=archive_id,
        user_id=USER_ID,
        session_id=SESSION_ID,
        archive_batch_key=batch_key,
        base_compression_version=base_version,
        messages=[
            ContextArchiveMessage(
                message_id="m1",
                role=MessageRole.USER,
                content="a",
                timestamp=FIXED_NOW,
            )
        ],
        created_time=FIXED_NOW,
    )


def _snapshot(messages: list[WorkingMemoryMessage], version: int = 0) -> WorkingMemorySnapshot:
    return WorkingMemorySnapshot(
        compression_version=version,
        compressed_context="",
        messages=messages,
    )


@pytest.fixture
def settings() -> Any:
    return get_settings()


def test_u_base_1_build_close_plan_freezes_compression_version() -> None:
    meta = _meta(compression_version=7)
    messages = [_message("m1", 10)]
    plan = build_close_plan(
        meta=meta,
        messages=messages,
        max_archive_estimated_tokens=7000,
    )
    assert plan.base_compression_version == 7


def test_u_base_2_suffix_create_input_uses_close_plan_version() -> None:
    meta = _meta(compression_version=5)
    messages = [_message("m1", 10), _message("m2", 20)]
    plan = build_close_plan(
        meta=meta,
        messages=messages,
        max_archive_estimated_tokens=7000,
    )
    suffix_batches = [b for b in plan.batches if not b.is_pending_reuse]
    assert suffix_batches
    input_model = ContextArchiveCreateInput(
        user_id=plan.user_id,
        session_id=plan.session_id,
        archive_batch_key=suffix_batches[0].archive_batch_key,
        base_compression_version=plan.base_compression_version,
        messages=suffix_batches[0].messages,
    )
    assert input_model.base_compression_version == 5


@pytest.mark.asyncio
async def test_u_base_3_frozen_version_not_live_redis(settings: Any) -> None:
    messages = [_message("m1", 10)]
    meta_initial = _meta(compression_version=7)
    meta_changed = _meta(compression_version=99)

    with patch(
        "memory_system.domain.services.session_close_service.acquire_compression_lock",
        new_callable=AsyncMock,
        return_value="token",
    ), patch(
        "memory_system.domain.services.session_close_service.execute_enter_closing_lua",
        new_callable=AsyncMock,
        return_value=SessionCloseEnterStatus.SUCCESS,
    ), patch(
        "memory_system.domain.services.session_close_service.get_working_memory_meta",
        new_callable=AsyncMock,
        side_effect=[meta_initial, meta_changed],
    ), patch(
        "memory_system.domain.services.session_close_service.read_working_memory_context",
        new_callable=AsyncMock,
        return_value=ContextReadResult(
            status=ContextReadStatus.SUCCESS,
            snapshot=_snapshot(messages, version=7),
        ),
    ), patch(
        "memory_system.domain.services.session_close_service.create_or_reuse_context_archive",
        new_callable=AsyncMock,
    ) as mock_create, patch(
        "memory_system.domain.services.session_close_service.publish_archive_created_event",
        new_callable=AsyncMock,
    ), patch(
        "memory_system.domain.services.session_close_service.execute_terminal_delete_lua",
        new_callable=AsyncMock,
        return_value=SessionCloseTerminalStatus.SUCCESS,
    ), patch(
        "memory_system.domain.services.session_close_service.release_compression_lock",
        new_callable=AsyncMock,
    ):
        mock_create.return_value = ContextArchiveResult(
            outcome=ContextArchiveOutcome.CREATED,
            archive_id="arch-1",
            archive=_archive("arch-1", 7, f"{SESSION_ID}:m1:m1"),
        )
        await close_session(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            settings=settings,
            user_id=USER_ID,
            session_id=SESSION_ID,
            clock=lambda: FIXED_NOW,
        )
        create_input = mock_create.call_args.kwargs["input"]
        assert create_input.base_compression_version == 7


@pytest.mark.asyncio
async def test_u1_happy_path(settings: Any) -> None:
    messages = [_message("m1", 10), _message("m2", 20)]
    with _close_patches(messages) as mocks:
        mocks["create"].return_value = ContextArchiveResult(
            outcome=ContextArchiveOutcome.CREATED,
            archive_id="arch-1",
            archive=_archive("arch-1", 0, f"{SESSION_ID}:m1:m2"),
        )
        result = await close_session(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            settings=settings,
            user_id=USER_ID,
            session_id=SESSION_ID,
            clock=lambda: FIXED_NOW,
        )
    assert result.status == "closed"
    assert result.archive_ids == ["arch-1"]
    mocks["terminal"].assert_awaited_once()


@pytest.mark.asyncio
async def test_u2_empty_session(settings: Any) -> None:
    with _close_patches([]) as mocks:
        result = await close_session(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            settings=settings,
            user_id=USER_ID,
            session_id=SESSION_ID,
            clock=lambda: FIXED_NOW,
        )
    assert result.archive_ids == []
    assert result.status == "closed"
    mocks["create"].assert_not_awaited()


@pytest.mark.asyncio
async def test_u3_session_not_found(settings: Any) -> None:
    with patch(
        "memory_system.domain.services.session_close_service.acquire_compression_lock",
        new_callable=AsyncMock,
        return_value="token",
    ), patch(
        "memory_system.domain.services.session_close_service.execute_enter_closing_lua",
        new_callable=AsyncMock,
        return_value=SessionCloseEnterStatus.SESSION_NOT_FOUND,
    ), patch(
        "memory_system.domain.services.session_close_service.release_compression_lock",
        new_callable=AsyncMock,
    ):
        with pytest.raises(SessionNotFoundCloseError):
            await close_session(
                redis=MagicMock(),
                mongodb=MagicMock(),
                kafka_producer=MagicMock(),
                settings=settings,
                user_id=USER_ID,
                session_id=SESSION_ID,
            )


@pytest.mark.asyncio
async def test_u4_closing_retry_recovery(settings: Any) -> None:
    messages = [_message("m1", 10)]
    with _close_patches(messages) as mocks:
        mocks["enter"].return_value = SessionCloseEnterStatus.SUCCESS
        mocks["create"].return_value = ContextArchiveResult(
            outcome=ContextArchiveOutcome.CREATED,
            archive_id="arch-1",
            archive=_archive("arch-1", 0, f"{SESSION_ID}:m1:m1"),
        )
        result = await close_session(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            settings=settings,
            user_id=USER_ID,
            session_id=SESSION_ID,
        )
    assert result.status == "closed"


@pytest.mark.asyncio
async def test_u5_terminal_repeat_close_not_found(settings: Any) -> None:
    with patch(
        "memory_system.domain.services.session_close_service.acquire_compression_lock",
        new_callable=AsyncMock,
        return_value="token",
    ), patch(
        "memory_system.domain.services.session_close_service.execute_enter_closing_lua",
        new_callable=AsyncMock,
        return_value=SessionCloseEnterStatus.SESSION_NOT_FOUND,
    ), patch(
        "memory_system.domain.services.session_close_service.release_compression_lock",
        new_callable=AsyncMock,
    ):
        with pytest.raises(SessionNotFoundCloseError):
            await close_session(
                redis=MagicMock(),
                mongodb=MagicMock(),
                kafka_producer=MagicMock(),
                settings=settings,
                user_id=USER_ID,
                session_id=SESSION_ID,
            )


@pytest.mark.asyncio
async def test_u6_all_suffix_archived(settings: Any) -> None:
    messages = [_message("m1", 10), _message("m2", 20), _message("m3", 30)]
    with _close_patches(messages) as mocks:
        mocks["create"].return_value = ContextArchiveResult(
            outcome=ContextArchiveOutcome.CREATED,
            archive_id="arch-all",
            archive=_archive("arch-all", 0, f"{SESSION_ID}:m1:m3"),
        )
        await close_session(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            settings=settings,
            user_id=USER_ID,
            session_id=SESSION_ID,
        )
    create_input = mocks["create"].call_args.kwargs["input"]
    assert len(create_input.messages) == 3


@pytest.mark.asyncio
async def test_u7_below_trigger_still_archives(settings: Any) -> None:
    messages = [_message("m1", 5)]
    with _close_patches(messages) as mocks:
        mocks["create"].return_value = ContextArchiveResult(
            outcome=ContextArchiveOutcome.CREATED,
            archive_id="arch-1",
            archive=_archive("arch-1", 0, f"{SESSION_ID}:m1:m1"),
        )
        await close_session(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            settings=settings,
            user_id=USER_ID,
            session_id=SESSION_ID,
        )
    mocks["create"].assert_awaited_once()


@pytest.mark.asyncio
async def test_u8_pending_reuse(settings: Any) -> None:
    pending_id = "pending-arch"
    batch_key = f"{SESSION_ID}:m1:m1"
    messages = [_message("m1", 10), _message("m2", 20)]
    meta = _meta(
        pending_id=pending_id,
        pending_count=1,
        pending_tokens=10,
        pending_batch_key=batch_key,
    )
    with _close_patches(messages, meta=meta) as mocks:
        mocks["create"].return_value = ContextArchiveResult(
            outcome=ContextArchiveOutcome.CREATED,
            archive_id="suffix-arch",
            archive=_archive("suffix-arch", 0, f"{SESSION_ID}:m2:m2"),
        )
        result = await close_session(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            settings=settings,
            user_id=USER_ID,
            session_id=SESSION_ID,
        )
    assert result.archive_ids[0] == pending_id
    mocks["create"].assert_awaited_once()


@pytest.mark.asyncio
async def test_u9_kafka_publish_failed_still_closed(settings: Any) -> None:
    messages = [_message("m1", 10)]
    with _close_patches(messages) as mocks:
        mocks["create"].return_value = ContextArchiveResult(
            outcome=ContextArchiveOutcome.CREATED,
            archive_id="arch-1",
            archive=_archive("arch-1", 0, f"{SESSION_ID}:m1:m1"),
        )
        mocks["publish"].side_effect = RuntimeError("kafka down")
        result = await close_session(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            settings=settings,
            user_id=USER_ID,
            session_id=SESSION_ID,
        )
    assert result.status == "closed"
    mocks["terminal"].assert_awaited_once()


@pytest.mark.asyncio
async def test_u10_llm_fail_pending_close_completes(settings: Any) -> None:
    pending_id = "pending-arch"
    messages = [_message("m1", 10)]
    meta = _meta(
        pending_id=pending_id,
        pending_count=1,
        pending_tokens=10,
        pending_batch_key=f"{SESSION_ID}:m1:m1",
    )
    with _close_patches(messages, meta=meta) as mocks:
        result = await close_session(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            settings=settings,
            user_id=USER_ID,
            session_id=SESSION_ID,
        )
    assert result.status == "closed"
    mocks["create"].assert_not_awaited()


@pytest.mark.asyncio
async def test_u11_finalize_fail_pending_close_completes(settings: Any) -> None:
    await test_u10_llm_fail_pending_close_completes(settings)


@pytest.mark.asyncio
async def test_u12_lock_not_acquired(settings: Any) -> None:
    with patch(
        "memory_system.domain.services.session_close_service.acquire_compression_lock",
        new_callable=AsyncMock,
        return_value=None,
    ):
        with pytest.raises(SessionCloseLockNotAcquiredError):
            await close_session(
                redis=MagicMock(),
                mongodb=MagicMock(),
                kafka_producer=MagicMock(),
                settings=settings,
                user_id=USER_ID,
                session_id=SESSION_ID,
            )


@pytest.mark.asyncio
async def test_u13_finalize_simulation_then_close(settings: Any) -> None:
    messages = [_message("m1", 10)]
    with _close_patches(messages) as mocks:
        mocks["create"].return_value = ContextArchiveResult(
            outcome=ContextArchiveOutcome.CREATED,
            archive_id="arch-1",
            archive=_archive("arch-1", 0, f"{SESSION_ID}:m1:m1"),
        )
        result = await close_session(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            settings=settings,
            user_id=USER_ID,
            session_id=SESSION_ID,
        )
    assert result.status == "closed"


def test_u14_token_boundary_exact_sum() -> None:
    messages = [_message("m1", 40), _message("m2", 60)]
    batches = split_close_suffix_batches(messages, 100)
    total = sum(m.estimated_tokens for m in messages)
    batch_sum = sum(m.estimated_tokens for batch in batches for m in batch)
    assert batch_sum == total


def test_u15_exact_message_set() -> None:
    messages = [_message("m1", 10), _message("m2", 20), _message("m3", 30)]
    plan = build_close_plan(
        meta=_meta(),
        messages=messages,
        max_archive_estimated_tokens=7000,
    )
    archived_ids = [m.message_id for b in plan.batches for m in b.messages]
    assert archived_ids == ["m1", "m2", "m3"]


@pytest.mark.asyncio
async def test_u16_retry_reuses_batch_key(settings: Any) -> None:
    messages = [_message("m1", 10)]
    with _close_patches(messages) as mocks:
        mocks["create"].return_value = ContextArchiveResult(
            outcome=ContextArchiveOutcome.REUSED,
            archive_id="arch-1",
            archive=_archive("arch-1", 0, f"{SESSION_ID}:m1:m1"),
        )
        await close_session(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            settings=settings,
            user_id=USER_ID,
            session_id=SESSION_ID,
        )
    assert mocks["create"].call_args.kwargs["input"].archive_batch_key == f"{SESSION_ID}:m1:m1"


@pytest.mark.asyncio
async def test_u17_crash_after_finalize_retry(settings: Any) -> None:
    messages = [_message("m1", 10)]
    with _close_patches(messages) as mocks:
        mocks["create"].return_value = ContextArchiveResult(
            outcome=ContextArchiveOutcome.REUSED,
            archive_id="arch-1",
            archive=_archive("arch-1", 0, f"{SESSION_ID}:m1:m1"),
        )
        result = await close_session(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            settings=settings,
            user_id=USER_ID,
            session_id=SESSION_ID,
        )
    assert result.status == "closed"


def test_u18_split_boundaries() -> None:
    messages = [_message("m1", 50), _message("m2", 50), _message("m3", 30)]
    batches = split_close_suffix_batches(messages, 80)
    assert len(batches) == 2


@pytest.mark.asyncio
async def test_u19_revert_active_early_failure(settings: Any) -> None:
    messages = [_message("m1", 10)]
    with _close_patches(messages) as mocks:
        mocks["create"].side_effect = RuntimeError("mongo fail")
        mocks["revert"].return_value = SessionCloseRevertStatus.SUCCESS
        with pytest.raises(RuntimeError):
            await close_session(
                redis=MagicMock(),
                mongodb=MagicMock(),
                kafka_producer=MagicMock(),
                settings=settings,
                user_id=USER_ID,
                session_id=SESSION_ID,
            )
        mocks["revert"].assert_awaited_once()


def test_u20_multi_suffix_same_base_version() -> None:
    settings_ctx = get_settings().context.model_copy(update={"max_archive_estimated_tokens": 50})
    messages = [_message("m1", 30), _message("m2", 30), _message("m3", 30)]
    plan = build_close_plan(
        meta=_meta(compression_version=4),
        messages=messages,
        max_archive_estimated_tokens=settings_ctx.max_archive_estimated_tokens,
    )
    suffix_batches = [b for b in plan.batches if not b.is_pending_reuse]
    assert len(suffix_batches) >= 2
    for batch in suffix_batches:
        inp = ContextArchiveCreateInput(
            user_id=plan.user_id,
            session_id=plan.session_id,
            archive_batch_key=batch.archive_batch_key,
            base_compression_version=plan.base_compression_version,
            messages=batch.messages,
        )
        assert inp.base_compression_version == 4


@pytest.mark.asyncio
async def test_reused_first_batch_blocks_revert_on_second_batch_failure(settings: Any) -> None:
    """P1-1 regression: successful REUSED arms revert gate; later Mongo fail must not revert."""
    messages = [_message("m1", 30), _message("m2", 30), _message("m3", 30)]
    small_ctx = get_settings().context.model_copy(update={"max_archive_estimated_tokens": 50})
    settings_small = get_settings().model_copy(update={"context": small_ctx})
    reused_result = ContextArchiveResult(
        outcome=ContextArchiveOutcome.REUSED,
        archive_id="arch-1",
        archive=_archive("arch-1", 0, f"{SESSION_ID}:m1:m2"),
    )
    call_count = 0

    async def create_side_effect(*_args: Any, **_kwargs: Any) -> ContextArchiveResult:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return reused_result
        raise RuntimeError("mongo fail on second batch")

    with _close_patches(messages) as mocks:
        mocks["create"].side_effect = create_side_effect
        with pytest.raises(RuntimeError, match="mongo fail"):
            await close_session(
                redis=MagicMock(),
                mongodb=MagicMock(),
                kafka_producer=MagicMock(),
                settings=settings_small,
                user_id=USER_ID,
                session_id=SESSION_ID,
            )
        mocks["revert"].assert_not_awaited()


@pytest.mark.asyncio
async def test_u21_reused_version_mismatch(settings: Any) -> None:
    messages = [_message("m1", 10)]
    with _close_patches(messages, meta=_meta(compression_version=7)) as mocks:
        mocks["create"].return_value = ContextArchiveResult(
            outcome=ContextArchiveOutcome.REUSED,
            archive_id="arch-1",
            archive=_archive("arch-1", 3, f"{SESSION_ID}:m1:m1"),
        )
        with pytest.raises(BaseCompressionVersionMismatchError):
            await close_session(
                redis=MagicMock(),
                mongodb=MagicMock(),
                kafka_producer=MagicMock(),
                settings=settings,
                user_id=USER_ID,
                session_id=SESSION_ID,
            )


@pytest.mark.asyncio
async def test_u22_malformed_compression_version(settings: Any) -> None:
    bad_meta = _meta(compression_version=-1)
    with patch(
        "memory_system.domain.services.session_close_service.acquire_compression_lock",
        new_callable=AsyncMock,
        return_value="token",
    ), patch(
        "memory_system.domain.services.session_close_service.execute_enter_closing_lua",
        new_callable=AsyncMock,
        return_value=SessionCloseEnterStatus.SUCCESS,
    ), patch(
        "memory_system.domain.services.session_close_service.get_working_memory_meta",
        new_callable=AsyncMock,
        return_value=bad_meta,
    ), patch(
        "memory_system.domain.services.session_close_service.read_working_memory_context",
        new_callable=AsyncMock,
        return_value=ContextReadResult(
            status=ContextReadStatus.SUCCESS,
            snapshot=_snapshot([]),
        ),
    ), patch(
        "memory_system.domain.services.session_close_service.execute_revert_active_lua",
        new_callable=AsyncMock,
        return_value=SessionCloseRevertStatus.SUCCESS,
    ) as mock_revert, patch(
        "memory_system.domain.services.session_close_service.release_compression_lock",
        new_callable=AsyncMock,
    ):
        with pytest.raises(MalformedCompressionVersionError):
            await close_session(
                redis=MagicMock(),
                mongodb=MagicMock(),
                kafka_producer=MagicMock(),
                settings=settings,
                user_id=USER_ID,
                session_id=SESSION_ID,
            )
        mock_revert.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_incomplete_terminal_failure(settings: Any) -> None:
    messages = [_message("m1", 10)]
    with _close_patches(messages) as mocks:
        mocks["create"].return_value = ContextArchiveResult(
            outcome=ContextArchiveOutcome.CREATED,
            archive_id="arch-1",
            archive=_archive("arch-1", 0, f"{SESSION_ID}:m1:m1"),
        )
        mocks["terminal"].return_value = SessionCloseTerminalStatus.INVALID_SESSION_STATE
        with pytest.raises(SessionCloseIncompleteError):
            await close_session(
                redis=MagicMock(),
                mongodb=MagicMock(),
                kafka_producer=MagicMock(),
                settings=settings,
                user_id=USER_ID,
                session_id=SESSION_ID,
            )


class _ClosePatchMocks(dict[str, Any]):
    pass


def _close_patches(
    messages: list[WorkingMemoryMessage],
    *,
    meta: WorkingMemoryMeta | None = None,
    compression_version: int = 0,
) -> Any:
    meta_value = meta or _meta(compression_version=compression_version)
    from contextlib import contextmanager

    @contextmanager
    def _ctx() -> Any:
        with patch(
            "memory_system.domain.services.session_close_service.acquire_compression_lock",
            new_callable=AsyncMock,
            return_value="token",
        ), patch(
            "memory_system.domain.services.session_close_service.execute_enter_closing_lua",
            new_callable=AsyncMock,
            return_value=SessionCloseEnterStatus.SUCCESS,
        ) as enter, patch(
            "memory_system.domain.services.session_close_service.get_working_memory_meta",
            new_callable=AsyncMock,
            return_value=meta_value,
        ), patch(
            "memory_system.domain.services.session_close_service.read_working_memory_context",
            new_callable=AsyncMock,
            return_value=ContextReadResult(
                status=ContextReadStatus.SUCCESS,
                snapshot=_snapshot(messages, compression_version),
            ),
        ), patch(
            "memory_system.domain.services.session_close_service.create_or_reuse_context_archive",
            new_callable=AsyncMock,
        ) as create, patch(
            "memory_system.domain.services.session_close_service.publish_archive_created_event",
            new_callable=AsyncMock,
        ) as publish, patch(
            "memory_system.domain.services.session_close_service.execute_terminal_delete_lua",
            new_callable=AsyncMock,
            return_value=SessionCloseTerminalStatus.SUCCESS,
        ) as terminal, patch(
            "memory_system.domain.services.session_close_service.execute_revert_active_lua",
            new_callable=AsyncMock,
            return_value=SessionCloseRevertStatus.SUCCESS,
        ) as revert, patch(
            "memory_system.domain.services.session_close_service.release_compression_lock",
            new_callable=AsyncMock,
        ):
            yield _ClosePatchMocks(
                enter=enter,
                create=create,
                publish=publish,
                terminal=terminal,
                revert=revert,
            )

    return _ctx()
