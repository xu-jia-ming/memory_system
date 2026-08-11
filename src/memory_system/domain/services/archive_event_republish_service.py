"""Archive event republish service (STM-011; Mongo read-only + Kafka publish)."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from pymongo import AsyncMongoClient

from memory_system.domain.enums.archive_event_republish import ArchiveEventRepublishStatus
from memory_system.domain.models.archive_created_event import (
    ARCHIVE_CREATED_EVENT_TYPE,
    ArchiveCreatedEvent,
)
from memory_system.domain.models.archive_event_republish import (
    ArchiveEventRepublishInput,
    ArchiveEventRepublishResult,
)
from memory_system.infrastructure.kafka.archive_created_publisher import (
    KafkaProducerLike,
    publish_archive_created_event,
)
from memory_system.infrastructure.mongodb.context_archive_repository import (
    find_context_archive_by_id,
)


async def republish_archive_created_event(
    *,
    mongodb: AsyncMongoClient[Any],
    kafka_producer: KafkaProducerLike,
    topic: str,
    input: ArchiveEventRepublishInput,
    logger: logging.Logger | None = None,
) -> ArchiveEventRepublishResult:
    """Load archive from Mongo (read-only) and republish context.archive.created."""
    log = logger or logging.getLogger(__name__)

    archive_id = input.archive_id.strip()
    if not archive_id:
        return ArchiveEventRepublishResult(
            status=ArchiveEventRepublishStatus.INVALID_INPUT,
            event_id=None,
        )

    try:
        archive = await find_context_archive_by_id(mongodb, archive_id)
    except ValueError:
        log.error("invalid archive document archive_id=%s", archive_id)
        return ArchiveEventRepublishResult(
            status=ArchiveEventRepublishStatus.INVALID_ARCHIVE,
            event_id=None,
        )

    if archive is None:
        return ArchiveEventRepublishResult(
            status=ArchiveEventRepublishStatus.ARCHIVE_NOT_FOUND,
            event_id=None,
        )

    if input.expected_user_id is not None and archive.user_id != input.expected_user_id:
        return ArchiveEventRepublishResult(
            status=ArchiveEventRepublishStatus.ARCHIVE_OWNERSHIP_MISMATCH,
            event_id=None,
        )

    event_id = str(uuid.uuid4())
    event = ArchiveCreatedEvent(
        event_id=event_id,
        event_type=ARCHIVE_CREATED_EVENT_TYPE,
        archive_id=archive.archive_id,
        user_id=archive.user_id,
        session_id=archive.session_id,
        created_time=archive.created_time,
    )

    try:
        await publish_archive_created_event(kafka_producer, topic, event)
    except Exception:
        log.error("kafka publish failed archive_id=%s", archive_id, exc_info=True)
        return ArchiveEventRepublishResult(
            status=ArchiveEventRepublishStatus.KAFKA_PUBLISH_FAILED,
            event_id=None,
        )

    return ArchiveEventRepublishResult(
        status=ArchiveEventRepublishStatus.SUCCESS,
        event_id=event_id,
    )
