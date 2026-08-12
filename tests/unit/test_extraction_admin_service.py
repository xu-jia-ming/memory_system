"""Unit tests for extraction_admin_service (EXT-008)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from memory_system.domain.enums.archive_event_republish import ArchiveEventRepublishStatus
from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.domain.models.archive_event_republish import ArchiveEventRepublishResult
from memory_system.domain.models.extraction_task import ExtractionLastError, MemoryExtractionTask
from memory_system.domain.services.extraction_admin_service import (
    ExtractionAdminInfrastructureError,
    ExtractionTaskNotFoundError,
    RetryNotAllowedError,
    get_status,
    rebuild_task,
    retry_task,
)
from memory_system.settings.models import Settings, get_settings

NOW = 1_700_000_100
TASK_ID = "11111111-1111-4111-8111-111111111111"
USER_ID = "user_001"
ARCHIVE_ID = "archive_000001"
EXTRACTION_RESULT = {"candidates": [{"memory_id": "m1"}]}


def _failed_task(
    error_code: str,
    *,
    status: ExtractionTaskStatus = ExtractionTaskStatus.FAILED,
    extraction_result: dict[str, Any] | None = EXTRACTION_RESULT,
) -> MemoryExtractionTask:
    return MemoryExtractionTask(
        task_id=TASK_ID,
        archive_id=ARCHIVE_ID,
        user_id=USER_ID,
        status=status,
        attempt_count=2,
        extraction_result=extraction_result,
        last_error=ExtractionLastError(
            error_code=error_code,
            failed_stage="llm_extraction",
            message="synthetic failure",
        ),
        created_time=NOW - 100,
        updated_time=NOW - 50,
        completed_time=None,
    )


def _pending_task() -> MemoryExtractionTask:
    return MemoryExtractionTask(
        task_id=TASK_ID,
        archive_id=ARCHIVE_ID,
        user_id=USER_ID,
        status=ExtractionTaskStatus.PENDING,
        attempt_count=2,
        extraction_result=EXTRACTION_RESULT,
        last_error=None,
        created_time=NOW - 100,
        updated_time=NOW,
        completed_time=None,
    )


@pytest.fixture
def settings() -> Settings:
    return get_settings()


@pytest.mark.asyncio
async def test_u1_get_found() -> None:
    task = _failed_task("llm_timeout")
    task = task.model_copy(update={"status": ExtractionTaskStatus.COMPLETED, "completed_time": NOW})
    mongodb = MagicMock()
    with patch(
        "memory_system.domain.services.extraction_admin_service.repo.find_extraction_task_by_user_and_archive_id",
        AsyncMock(return_value=task),
    ):
        result = await get_status(mongodb, USER_ID, ARCHIVE_ID)
    assert result.status == ExtractionTaskStatus.COMPLETED
    assert result.attempt_count == 2
    assert result.last_error is not None
    assert result.completed_time == NOW


@pytest.mark.asyncio
async def test_u2_get_user_mismatch() -> None:
    mongodb = MagicMock()
    with patch(
        "memory_system.domain.services.extraction_admin_service.repo.find_extraction_task_by_user_and_archive_id",
        AsyncMock(return_value=None),
    ):
        with pytest.raises(ExtractionTaskNotFoundError):
            await get_status(mongodb, USER_ID, ARCHIVE_ID)


@pytest.mark.asyncio
async def test_u3_retry_allowed_code(settings: Settings) -> None:
    failed = _failed_task("llm_timeout")
    pending = _pending_task()
    mongodb = MagicMock()
    kafka_producer = MagicMock()
    with (
        patch(
            "memory_system.domain.services.extraction_admin_service.repo.find_extraction_task_by_user_and_archive_id",
            AsyncMock(return_value=failed),
        ),
        patch(
            "memory_system.domain.services.extraction_admin_service.repo.admin_reset_failed_to_pending",
            AsyncMock(return_value=pending),
        ),
        patch(
            "memory_system.domain.services.extraction_admin_service.republish_archive_created_event",
            AsyncMock(
                return_value=ArchiveEventRepublishResult(
                    status=ArchiveEventRepublishStatus.SUCCESS,
                    event_id="22222222-2222-4222-8222-222222222222",
                )
            ),
        ),
    ):
        result = await retry_task(
            mongodb, kafka_producer, settings, USER_ID, ARCHIVE_ID, NOW
        )
    assert result.status == ExtractionTaskStatus.PENDING


@pytest.mark.asyncio
async def test_u4_retry_permanent_code(settings: Settings) -> None:
    failed = _failed_task("archive_not_found")
    mongodb = MagicMock()
    kafka_producer = MagicMock()
    with patch(
        "memory_system.domain.services.extraction_admin_service.repo.find_extraction_task_by_user_and_archive_id",
        AsyncMock(return_value=failed),
    ):
        with pytest.raises(RetryNotAllowedError):
            await retry_task(
                mongodb, kafka_producer, settings, USER_ID, ARCHIVE_ID, NOW
            )


@pytest.mark.asyncio
async def test_u5_retry_reconciliation_plan_conflict(settings: Settings) -> None:
    failed = _failed_task("reconciliation_plan_conflict")
    mongodb = MagicMock()
    kafka_producer = MagicMock()
    with patch(
        "memory_system.domain.services.extraction_admin_service.repo.find_extraction_task_by_user_and_archive_id",
        AsyncMock(return_value=failed),
    ):
        with pytest.raises(RetryNotAllowedError):
            await retry_task(
                mongodb, kafka_producer, settings, USER_ID, ARCHIVE_ID, NOW
            )


@pytest.mark.asyncio
async def test_u6_rebuild_conflict_only(settings: Settings) -> None:
    failed = _failed_task("reconciliation_plan_conflict")
    pending = _pending_task().model_copy(update={"extraction_result": None})
    mongodb = MagicMock()
    kafka_producer = MagicMock()
    reset_mock = AsyncMock(return_value=pending)
    with (
        patch(
            "memory_system.domain.services.extraction_admin_service.repo.find_extraction_task_by_user_and_archive_id",
            AsyncMock(return_value=failed),
        ),
        patch(
            "memory_system.domain.services.extraction_admin_service.repo.admin_reset_failed_to_pending",
            reset_mock,
        ),
        patch(
            "memory_system.domain.services.extraction_admin_service.republish_archive_created_event",
            AsyncMock(
                return_value=ArchiveEventRepublishResult(
                    status=ArchiveEventRepublishStatus.SUCCESS,
                    event_id="22222222-2222-4222-8222-222222222222",
                )
            ),
        ),
    ):
        result = await rebuild_task(
            mongodb, kafka_producer, settings, USER_ID, ARCHIVE_ID, NOW
        )
    assert result.status == ExtractionTaskStatus.PENDING
    assert reset_mock.await_args.kwargs["clear_extraction_result"] is True


@pytest.mark.asyncio
async def test_u7_rebuild_wrong_code(settings: Settings) -> None:
    failed = _failed_task("llm_timeout")
    mongodb = MagicMock()
    kafka_producer = MagicMock()
    with patch(
        "memory_system.domain.services.extraction_admin_service.repo.find_extraction_task_by_user_and_archive_id",
        AsyncMock(return_value=failed),
    ):
        with pytest.raises(RetryNotAllowedError):
            await rebuild_task(
                mongodb, kafka_producer, settings, USER_ID, ARCHIVE_ID, NOW
            )


@pytest.mark.asyncio
async def test_u8_retry_non_failed(settings: Settings) -> None:
    completed = _failed_task("llm_timeout").model_copy(
        update={"status": ExtractionTaskStatus.COMPLETED, "last_error": None}
    )
    mongodb = MagicMock()
    kafka_producer = MagicMock()
    with patch(
        "memory_system.domain.services.extraction_admin_service.repo.find_extraction_task_by_user_and_archive_id",
        AsyncMock(return_value=completed),
    ):
        with pytest.raises(RetryNotAllowedError):
            await retry_task(
                mongodb, kafka_producer, settings, USER_ID, ARCHIVE_ID, NOW
            )


@pytest.mark.asyncio
async def test_u9_kafka_publish_fail(settings: Settings) -> None:
    failed = _failed_task("kafka_publish_failed")
    pending = _pending_task()
    mongodb = MagicMock()
    kafka_producer = MagicMock()
    mark_failed_mock = AsyncMock(return_value=failed)
    with (
        patch(
            "memory_system.domain.services.extraction_admin_service.repo.find_extraction_task_by_user_and_archive_id",
            AsyncMock(return_value=failed),
        ),
        patch(
            "memory_system.domain.services.extraction_admin_service.repo.admin_reset_failed_to_pending",
            AsyncMock(return_value=pending),
        ),
        patch(
            "memory_system.domain.services.extraction_admin_service.republish_archive_created_event",
            AsyncMock(
                return_value=ArchiveEventRepublishResult(
                    status=ArchiveEventRepublishStatus.KAFKA_PUBLISH_FAILED,
                    event_id=None,
                )
            ),
        ),
        patch(
            "memory_system.domain.services.extraction_admin_service.repo.admin_mark_failed_from_admin_action",
            mark_failed_mock,
        ),
    ):
        with pytest.raises(ExtractionAdminInfrastructureError):
            await retry_task(
                mongodb, kafka_producer, settings, USER_ID, ARCHIVE_ID, NOW
            )
    last_error = mark_failed_mock.await_args.kwargs["last_error"]
    assert last_error.error_code == "kafka_publish_failed"
    assert last_error.failed_stage == "extraction_admin"


@pytest.mark.asyncio
async def test_u10_republish_archive_mismatch(settings: Settings) -> None:
    failed = _failed_task("llm_timeout")
    pending = _pending_task()
    mongodb = MagicMock()
    kafka_producer = MagicMock()
    mark_failed_mock = AsyncMock(return_value=failed)
    with (
        patch(
            "memory_system.domain.services.extraction_admin_service.repo.find_extraction_task_by_user_and_archive_id",
            AsyncMock(return_value=failed),
        ),
        patch(
            "memory_system.domain.services.extraction_admin_service.repo.admin_reset_failed_to_pending",
            AsyncMock(return_value=pending),
        ),
        patch(
            "memory_system.domain.services.extraction_admin_service.republish_archive_created_event",
            AsyncMock(
                return_value=ArchiveEventRepublishResult(
                    status=ArchiveEventRepublishStatus.ARCHIVE_OWNERSHIP_MISMATCH,
                    event_id=None,
                )
            ),
        ),
        patch(
            "memory_system.domain.services.extraction_admin_service.repo.admin_mark_failed_from_admin_action",
            mark_failed_mock,
        ),
    ):
        with pytest.raises(ExtractionAdminInfrastructureError):
            await retry_task(
                mongodb, kafka_producer, settings, USER_ID, ARCHIVE_ID, NOW
            )
    assert mark_failed_mock.await_count == 1


@pytest.mark.asyncio
async def test_u11_memory_search_text_too_long_retry_not_allowed(settings: Settings) -> None:
    failed = _failed_task("memory_search_text_too_long")
    mongodb = MagicMock()
    kafka_producer = MagicMock()
    with patch(
        "memory_system.domain.services.extraction_admin_service.repo.find_extraction_task_by_user_and_archive_id",
        AsyncMock(return_value=failed),
    ):
        with pytest.raises(RetryNotAllowedError):
            await retry_task(
                mongodb, kafka_producer, settings, USER_ID, ARCHIVE_ID, NOW
            )
