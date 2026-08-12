"""Extraction admin GET / retry / rebuild orchestration (§2.1.14 / EXT-008)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict
from pymongo import AsyncMongoClient

from memory_system.domain.constants.extraction_retry_policy import (
    MANUAL_RETRY_ALLOWED_ERROR_CODES,
    REBUILD_ALLOWED_ERROR_CODES,
)
from memory_system.domain.enums.archive_event_republish import ArchiveEventRepublishStatus
from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.domain.models.archive_event_republish import ArchiveEventRepublishInput
from memory_system.domain.models.extraction_task import ExtractionLastError, MemoryExtractionTask
from memory_system.domain.services.archive_event_republish_service import (
    republish_archive_created_event,
)
from memory_system.infrastructure.kafka.archive_created_publisher import KafkaProducerLike
from memory_system.infrastructure.mongodb import extraction_task_repository as repo
from memory_system.settings.models import Settings

Clock = Callable[[], int]
_logger = structlog.get_logger(__name__)

ADMIN_FAILED_STAGE = "extraction_admin"
KAFKA_PUBLISH_FAILED_MESSAGE = "Kafka publish failed during extraction admin action"


class ExtractionTaskNotFoundError(Exception):
    """Task missing or user_id mismatch (HTTP 404)."""


class RetryNotAllowedError(Exception):
    """Business rule prevents retry/rebuild (HTTP 409)."""


class ExtractionAdminInfrastructureError(Exception):
    """Mongo/Kafka infrastructure failure (HTTP 503)."""


class ExtractionAdminGetResult(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    user_id: str
    archive_id: str
    status: ExtractionTaskStatus
    attempt_count: int
    last_error: ExtractionLastError | None
    completed_time: int | None


class ExtractionAdminMutationSuccess(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    user_id: str
    archive_id: str
    status: ExtractionTaskStatus = ExtractionTaskStatus.PENDING


def _map_task_to_get_result(task: MemoryExtractionTask) -> ExtractionAdminGetResult:
    return ExtractionAdminGetResult(
        user_id=task.user_id,
        archive_id=task.archive_id,
        status=task.status,
        attempt_count=task.attempt_count,
        last_error=task.last_error,
        completed_time=task.completed_time,
    )


def _kafka_publish_failed_error() -> ExtractionLastError:
    return ExtractionLastError(
        error_code="kafka_publish_failed",
        failed_stage=ADMIN_FAILED_STAGE,
        message=KAFKA_PUBLISH_FAILED_MESSAGE,
    )


async def get_status(
    mongodb: AsyncMongoClient[Any],
    user_id: str,
    archive_id: str,
) -> ExtractionAdminGetResult:
    task = await repo.find_extraction_task_by_user_and_archive_id(
        mongodb, user_id, archive_id
    )
    if task is None:
        raise ExtractionTaskNotFoundError()
    return _map_task_to_get_result(task)


async def retry_task(
    mongodb: AsyncMongoClient[Any],
    kafka_producer: KafkaProducerLike,
    settings: Settings,
    user_id: str,
    archive_id: str,
    now: int,
) -> ExtractionAdminMutationSuccess:
    return await _mutate_failed_to_pending_and_republish(
        mongodb=mongodb,
        kafka_producer=kafka_producer,
        settings=settings,
        user_id=user_id,
        archive_id=archive_id,
        now=now,
        clear_extraction_result=False,
        allowed_error_codes=MANUAL_RETRY_ALLOWED_ERROR_CODES,
        action="retry",
    )


async def rebuild_task(
    mongodb: AsyncMongoClient[Any],
    kafka_producer: KafkaProducerLike,
    settings: Settings,
    user_id: str,
    archive_id: str,
    now: int,
) -> ExtractionAdminMutationSuccess:
    return await _mutate_failed_to_pending_and_republish(
        mongodb=mongodb,
        kafka_producer=kafka_producer,
        settings=settings,
        user_id=user_id,
        archive_id=archive_id,
        now=now,
        clear_extraction_result=True,
        allowed_error_codes=REBUILD_ALLOWED_ERROR_CODES,
        action="rebuild",
    )


async def _mutate_failed_to_pending_and_republish(
    *,
    mongodb: AsyncMongoClient[Any],
    kafka_producer: KafkaProducerLike,
    settings: Settings,
    user_id: str,
    archive_id: str,
    now: int,
    clear_extraction_result: bool,
    allowed_error_codes: frozenset[str],
    action: str,
) -> ExtractionAdminMutationSuccess:
    task = await repo.find_extraction_task_by_user_and_archive_id(
        mongodb, user_id, archive_id
    )
    if task is None:
        raise ExtractionTaskNotFoundError()

    if task.status != ExtractionTaskStatus.FAILED:
        raise RetryNotAllowedError()

    if task.last_error is None or task.last_error.error_code not in allowed_error_codes:
        raise RetryNotAllowedError()

    try:
        updated = await repo.admin_reset_failed_to_pending(
            mongodb,
            user_id=user_id,
            archive_id=archive_id,
            now=now,
            clear_extraction_result=clear_extraction_result,
        )
    except Exception:
        _logger.error(
            "extraction_admin_mongo_reset_failed",
            action=action,
            task_id=task.task_id,
            archive_id=archive_id,
            user_id=user_id,
            attempt_count=task.attempt_count,
        )
        raise ExtractionAdminInfrastructureError() from None

    if updated is None:
        raise RetryNotAllowedError()

    republish_result = await republish_archive_created_event(
        mongodb=mongodb,
        kafka_producer=kafka_producer,
        topic=settings.kafka.topic,
        input=ArchiveEventRepublishInput(
            archive_id=archive_id,
            expected_user_id=user_id,
        ),
    )

    if republish_result.status != ArchiveEventRepublishStatus.SUCCESS:
        last_error = _kafka_publish_failed_error()
        _logger.error(
            "extraction_admin_kafka_publish_failed",
            action=action,
            task_id=updated.task_id,
            archive_id=archive_id,
            user_id=user_id,
            attempt_count=updated.attempt_count,
            failed_stage=last_error.failed_stage,
            error_code=last_error.error_code,
            republish_status=republish_result.status.value,
        )
        try:
            await repo.admin_mark_failed_from_admin_action(
                mongodb,
                user_id=user_id,
                archive_id=archive_id,
                last_error=last_error,
                now=now,
            )
        except Exception:
            _logger.error(
                "extraction_admin_mark_failed_after_kafka_failed",
                action=action,
                task_id=updated.task_id,
                archive_id=archive_id,
                user_id=user_id,
                attempt_count=updated.attempt_count,
                failed_stage=last_error.failed_stage,
            )
            raise ExtractionAdminInfrastructureError() from None
        raise ExtractionAdminInfrastructureError()

    _logger.info(
        "extraction_admin_mutation_success",
        action=action,
        task_id=updated.task_id,
        archive_id=archive_id,
        user_id=user_id,
        attempt_count=updated.attempt_count,
        status=ExtractionTaskStatus.PENDING.value,
    )

    return ExtractionAdminMutationSuccess(
        user_id=user_id,
        archive_id=archive_id,
    )
