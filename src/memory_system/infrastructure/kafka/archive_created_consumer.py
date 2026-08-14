"""Kafka consumer adapter for ``context.archive.created`` (EXT-001 C3/C4/C8)."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Final

from aiokafka import AIOKafkaConsumer, TopicPartition  # type: ignore[import-untyped]
from aiokafka.structs import ConsumerRecord  # type: ignore[import-untyped]
from pydantic import ValidationError
from pymongo import AsyncMongoClient

from memory_system.domain.models.archive_created_event import (
    ARCHIVE_CREATED_EVENT_FIELD_NAMES,
    ARCHIVE_CREATED_EVENT_TYPE,
    ArchiveCreatedEvent,
)
from memory_system.domain.services.extraction_pipeline_port import ExtractionPipelinePort
from memory_system.domain.services.extraction_task_consumer_service import (
    process_archive_created_event,
)
from memory_system.settings.models import KafkaConsumerSettings

MEMORY_EXTRACTION_CONSUMER_GROUP: Final[str] = "memory-extraction-group"


def remaining_shutdown_seconds(
    shutdown_started_monotonic: float | None,
    shutdown_timeout_seconds: int,
) -> float:
    if shutdown_started_monotonic is None:
        return float(shutdown_timeout_seconds)
    elapsed = time.monotonic() - shutdown_started_monotonic
    return max(0.0, float(shutdown_timeout_seconds) - elapsed)


_EMPTY_ID_FIELDS: Final[tuple[str, ...]] = (
    "archive_id",
    "user_id",
    "event_id",
    "session_id",
)


class MalformedArchiveCreatedEventError(ValueError):
    """Consumer-boundary reject: malformed payload (C4/C8); do not commit offset."""


class ArchiveCreatedKeyMismatchError(ValueError):
    """Message key ≠ event.user_id (C3.1); do not upsert/commit; stop processing."""


def validate_archive_created_payload_keys(payload: Mapping[str, Any]) -> None:
    """Exact six-key set against ``ARCHIVE_CREATED_EVENT_FIELD_NAMES`` (MF-001)."""
    actual = set(payload.keys())
    expected = set(ARCHIVE_CREATED_EVENT_FIELD_NAMES)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise MalformedArchiveCreatedEventError(
            f"archive created event keys mismatch missing={missing} extra={extra}"
        )


def reject_empty_string_ids(payload: Mapping[str, Any]) -> None:
    """Empty-string IDs are malformed (SF-005); exact ``\"\"`` only, no trim."""
    for field in _EMPTY_ID_FIELDS:
        value = payload.get(field)
        if value == "":
            raise MalformedArchiveCreatedEventError(
                f"archive created event empty-string id field={field}"
            )


def parse_archive_created_event_value(value: bytes) -> ArchiveCreatedEvent:
    """Decode UTF-8 JSON → exact-key boundary → empty-ID reject → model_validate."""
    try:
        text = value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MalformedArchiveCreatedEventError("value is not valid UTF-8") from exc

    try:
        raw: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MalformedArchiveCreatedEventError("value is not valid JSON") from exc

    if not isinstance(raw, dict):
        raise MalformedArchiveCreatedEventError("value JSON must be an object")

    validate_archive_created_payload_keys(raw)
    reject_empty_string_ids(raw)

    try:
        event = ArchiveCreatedEvent.model_validate(raw)
    except ValidationError as exc:
        raise MalformedArchiveCreatedEventError(
            f"archive created event model validation failed: {exc}"
        ) from exc

    if event.event_type != ARCHIVE_CREATED_EVENT_TYPE:
        raise MalformedArchiveCreatedEventError(
            f"invalid event_type={event.event_type!r}"
        )
    return event


def assert_message_key_matches_user_id(
    key: bytes | None,
    event: ArchiveCreatedEvent,
) -> None:
    """C3.1: Message Key UTF-8 must equal ``event.user_id`` exactly."""
    if key is None:
        raise ArchiveCreatedKeyMismatchError("kafka message key is missing")
    try:
        decoded = key.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ArchiveCreatedKeyMismatchError("kafka message key is not valid UTF-8") from exc
    if decoded != event.user_id:
        raise ArchiveCreatedKeyMismatchError(
            f"kafka message key mismatch key={decoded!r} event_user_id={event.user_id!r}"
        )


def create_archive_created_consumer(
    *,
    bootstrap_servers: str,
    topic: str,
    consumer_settings: KafkaConsumerSettings,
    group_id: str = MEMORY_EXTRACTION_CONSUMER_GROUP,
) -> AIOKafkaConsumer:
    """Build AIOKafkaConsumer with fail-closed manual commit settings."""
    if consumer_settings.enable_auto_commit is not False:
        raise ValueError("enable_auto_commit must be False for extraction consumer")
    if consumer_settings.max_poll_records != 1:
        raise ValueError("max_poll_records must be 1 for extraction consumer")

    return AIOKafkaConsumer(
        topic,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        enable_auto_commit=False,
        auto_offset_reset=consumer_settings.auto_offset_reset,
        session_timeout_ms=consumer_settings.session_timeout_ms,
        heartbeat_interval_ms=consumer_settings.heartbeat_interval_ms,
        max_poll_interval_ms=consumer_settings.max_poll_interval_ms,
        max_poll_records=1,
    )


async def commit_record_offset(
    consumer: AIOKafkaConsumer,
    record: ConsumerRecord[Any, Any],
) -> None:
    """Commit the offset immediately after the given record (exclusive next)."""
    tp = TopicPartition(record.topic, record.partition)
    await consumer.commit({tp: record.offset + 1})


async def process_consumer_record(
    *,
    record: ConsumerRecord[Any, Any],
    mongodb: AsyncMongoClient[Any],
    pipeline: ExtractionPipelinePort,
    clock: Callable[[], int],
    logger: logging.Logger | None = None,
) -> bool:
    """Parse + key-check + process one record. Returns whether offset should commit.

    Malformed / key mismatch raise (C8 / C3.1) — caller must not commit and must stop.
    """
    log = logger or logging.getLogger(__name__)
    event = parse_archive_created_event_value(record.value)
    try:
        assert_message_key_matches_user_id(record.key, event)
    except ArchiveCreatedKeyMismatchError:
        log.error(
            "archive created key mismatch archive_id=%s event_user_id=%s key=%r",
            event.archive_id,
            event.user_id,
            None if record.key is None else record.key[:64],
        )
        raise

    result = await process_archive_created_event(
        mongodb=mongodb,
        event=event,
        pipeline=pipeline,
        clock=clock,
        logger=log,
    )
    return result.should_commit_offset


async def run_archive_created_consumer_loop(
    *,
    consumer: AIOKafkaConsumer,
    mongodb: AsyncMongoClient[Any],
    pipeline: ExtractionPipelinePort,
    clock: Callable[[], int],
    logger: logging.Logger | None = None,
    should_stop: Callable[[], bool] | None = None,
    on_record: Callable[[ConsumerRecord[Any, Any], bool], Awaitable[None]] | None = None,
    max_records: int | None = None,
    idle_deadline_monotonic: float | None = None,
    get_shutdown_started: Callable[[], float | None] | None = None,
    shutdown_timeout_seconds: int = 0,
) -> int:
    """Serial poll loop (max 1). Commits only when processing returns True.

    Stops on malformed / key mismatch / terminal persist failure (propagates).
    Returns number of records successfully processed (including early-commit paths).

    ``idle_deadline_monotonic``: when set, return after this ``time.monotonic()``
    if no further records arrive (test harness stop condition).
    """
    log = logger or logging.getLogger(__name__)
    processed = 0
    while True:
        if should_stop is not None and should_stop():
            return processed
        if max_records is not None and processed >= max_records:
            return processed
        if idle_deadline_monotonic is not None and time.monotonic() >= idle_deadline_monotonic:
            return processed

        batch = await consumer.getmany(timeout_ms=1000, max_records=1)
        if not batch:
            continue

        for _tp, records in batch.items():
            for record in records:
                shutdown_started = (
                    get_shutdown_started() if get_shutdown_started is not None else None
                )
                try:
                    if shutdown_started is not None and shutdown_timeout_seconds > 0:
                        remaining = remaining_shutdown_seconds(
                            shutdown_started,
                            shutdown_timeout_seconds,
                        )
                        if remaining <= 0:
                            log.error(
                                "shutdown budget exhausted before in-flight record "
                                "topic=%s partition=%s offset=%s",
                                record.topic,
                                record.partition,
                                record.offset,
                            )
                            return processed
                        should_commit = await asyncio.wait_for(
                            process_consumer_record(
                                record=record,
                                mongodb=mongodb,
                                pipeline=pipeline,
                                clock=clock,
                                logger=log,
                            ),
                            timeout=remaining,
                        )
                    else:
                        should_commit = await process_consumer_record(
                            record=record,
                            mongodb=mongodb,
                            pipeline=pipeline,
                            clock=clock,
                            logger=log,
                        )
                except TimeoutError:
                    log.error(
                        "in-flight archive created record timed out during shutdown "
                        "topic=%s partition=%s offset=%s",
                        record.topic,
                        record.partition,
                        record.offset,
                    )
                    return processed
                except (MalformedArchiveCreatedEventError, ArchiveCreatedKeyMismatchError):
                    log.error(
                        "stopping consumer after fail-closed record topic=%s partition=%s "
                        "offset=%s",
                        record.topic,
                        record.partition,
                        record.offset,
                    )
                    raise

                if should_commit:
                    await commit_record_offset(consumer, record)
                if on_record is not None:
                    await on_record(record, should_commit)
                processed += 1
                if max_records is not None and processed >= max_records:
                    return processed
