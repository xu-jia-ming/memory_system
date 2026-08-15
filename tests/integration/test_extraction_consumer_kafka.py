"""Kafka + Mongo integration for archive-created consumer offset/idempotency (EXT-001)."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import patch

import pytest
from aiokafka import (  # type: ignore[import-untyped]
    AIOKafkaConsumer,
    AIOKafkaProducer,
    TopicPartition,
)
from pymongo import AsyncMongoClient

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.domain.models.archive_created_event import (
    ARCHIVE_CREATED_EVENT_TYPE,
    ArchiveCreatedEvent,
)
from memory_system.domain.models.extraction_task import ExtractionLastError, MemoryExtractionTask
from memory_system.domain.services.extraction_pipeline_port import PipelineTerminalDecision
from memory_system.domain.services.extraction_task_consumer_service import TerminalPersistError
from memory_system.infrastructure.kafka.archive_created_consumer import (
    MEMORY_EXTRACTION_CONSUMER_GROUP,
    ArchiveCreatedKeyMismatchError,
    MalformedArchiveCreatedEventError,
    create_archive_created_consumer,
    run_archive_created_consumer_loop,
)
from memory_system.infrastructure.mongodb import extraction_task_repository as repo
from memory_system.infrastructure.mongodb.extraction_task_repository import (
    MEMORY_EXTRACTION_TASK_COLLECTION,
    find_extraction_task_by_archive_id,
)
from memory_system.settings.models import KafkaConsumerSettings

pytest_plugins = ("tests.integration.support.mongo_kafka_fixtures",)

TOPIC = "context.archive.created"
FIXED_NOW = 1_700_000_000


class FakeCompletePipeline:
    def __init__(self) -> None:
        self.calls = 0

    async def run(
        self, task: MemoryExtractionTask, event: ArchiveCreatedEvent
    ) -> PipelineTerminalDecision:
        self.calls += 1
        return PipelineTerminalDecision.complete()


class FakeAbortThenComplete:
    def __init__(self) -> None:
        self.calls = 0

    async def run(
        self, task: MemoryExtractionTask, event: ArchiveCreatedEvent
    ) -> PipelineTerminalDecision:
        self.calls += 1
        if self.calls == 1:
            return PipelineTerminalDecision.abort_without_terminal()
        return PipelineTerminalDecision.complete()


class FakeFailPipeline:
    async def run(
        self, task: MemoryExtractionTask, event: ArchiveCreatedEvent
    ) -> PipelineTerminalDecision:
        return PipelineTerminalDecision.fail(
            ExtractionLastError(
                error_code="graph_write_failed",
                failed_stage="graph_write",
                message="injected",
            )
        )


@pytest.fixture(autouse=True)
async def _clean_tasks(mongo_client: AsyncMongoClient[Any]) -> AsyncIterator[None]:
    db = mongo_client.get_default_database()
    if db is not None:
        await db[MEMORY_EXTRACTION_TASK_COLLECTION].delete_many({})
    yield
    if db is not None:
        await db[MEMORY_EXTRACTION_TASK_COLLECTION].delete_many({})


def _new_event(**overrides: object) -> ArchiveCreatedEvent:
    suffix = uuid.uuid4().hex[:8]
    payload: dict[str, object] = {
        "event_id": str(uuid.uuid4()),
        "event_type": ARCHIVE_CREATED_EVENT_TYPE,
        "archive_id": str(uuid.uuid4()),
        "user_id": f"ext001_user_{suffix}",
        "session_id": str(uuid.uuid4()),
        "created_time": FIXED_NOW,
    }
    payload.update(overrides)
    return ArchiveCreatedEvent.model_validate(payload)


def _unique_group() -> str:
    # Unique group avoids cross-test pollution; factory default remains production constant.
    return f"{MEMORY_EXTRACTION_CONSUMER_GROUP}-t-{uuid.uuid4().hex[:10]}"


async def _committed_offset(
    bootstrap: str,
    *,
    group_id: str,
    topic: str,
    partition: int,
) -> int | None:
    consumer = AIOKafkaConsumer(
        bootstrap_servers=bootstrap,
        group_id=group_id,
        enable_auto_commit=False,
    )
    await consumer.start()
    try:
        tp = TopicPartition(topic, partition)
        consumer.assign([tp])
        return await consumer.committed(tp)
    finally:
        await consumer.stop()


async def _run_one(
    *,
    bootstrap: str,
    mongo_client: AsyncMongoClient[Any],
    pipeline: object,
    group_id: str,
    max_records: int = 1,
    timeout_s: float = 30.0,
    partition: int | None = None,
    start_offset: int | None = None,
) -> int:
    settings = KafkaConsumerSettings()
    assert settings.enable_auto_commit is False
    consumer = create_archive_created_consumer(
        bootstrap_servers=bootstrap,
        topic=TOPIC,
        consumer_settings=settings,
        group_id=group_id,
    )
    await consumer.start()
    try:
        if partition is not None:
            tp = TopicPartition(TOPIC, partition)
            # The production factory subscribes to the topic. Replace that
            # subscription before user-assigning the exact published partition.
            consumer.unsubscribe()
            consumer.assign([tp])
            if start_offset is not None:
                consumer.seek(tp, start_offset)
        return await run_archive_created_consumer_loop(
            consumer=consumer,
            mongodb=mongo_client,
            pipeline=pipeline,  # type: ignore[arg-type]
            clock=lambda: FIXED_NOW,
            max_records=max_records,
            idle_deadline_monotonic=time.monotonic() + timeout_s,
        )
    finally:
        await consumer.stop()


async def _publish_event(
    producer: AIOKafkaProducer,
    event: ArchiveCreatedEvent,
    *,
    key: bytes | None = None,
    value: bytes | None = None,
) -> tuple[int, int]:
    """Publish once; return (partition, offset)."""
    record_meta = await producer.send_and_wait(
        TOPIC,
        key=event.user_id.encode("utf-8") if key is None else key,
        value=event.to_json_bytes() if value is None else value,
    )
    return record_meta.partition, record_meta.offset


@pytest.mark.integration
@pytest.mark.asyncio
async def test_legal_event_commits_offset_same_group_no_redelivery(
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: AIOKafkaProducer,
    mongo_kafka_stack: tuple[str, str],
) -> None:
    _, bootstrap = mongo_kafka_stack
    event = _new_event()
    group_id = _unique_group()
    pipeline = FakeCompletePipeline()

    partition, offset = await _publish_event(kafka_producer, event)

    processed = await _run_one(
        bootstrap=bootstrap,
        mongo_client=mongo_client,
        pipeline=pipeline,
        group_id=group_id,
        partition=partition,
        start_offset=offset,
    )
    assert processed == 1
    assert pipeline.calls == 1

    task = await find_extraction_task_by_archive_id(mongo_client, event.archive_id)
    assert task is not None
    assert task.status == ExtractionTaskStatus.COMPLETED

    committed = await _committed_offset(
        bootstrap,
        group_id=group_id,
        topic=TOPIC,
        partition=partition,
    )
    assert committed == offset + 1

    pipeline2 = FakeCompletePipeline()
    processed_again = await _run_one(
        bootstrap=bootstrap,
        mongo_client=mongo_client,
        pipeline=pipeline2,
        group_id=group_id,
        max_records=1,
        timeout_s=5.0,
        partition=partition,
    )
    assert processed_again == 0
    assert pipeline2.calls == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_duplicate_delivery_completed_early_exit_no_second_pipeline(
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: AIOKafkaProducer,
    mongo_kafka_stack: tuple[str, str],
) -> None:
    _, bootstrap = mongo_kafka_stack
    event = _new_event()
    group_id = _unique_group()
    pipeline = FakeCompletePipeline()

    partition1, offset1 = await _publish_event(kafka_producer, event)
    assert await _run_one(
        bootstrap=bootstrap,
        mongo_client=mongo_client,
        pipeline=pipeline,
        group_id=group_id,
        partition=partition1,
        start_offset=offset1,
    ) == 1

    partition2, offset2 = await _publish_event(kafka_producer, event)
    pipeline2 = FakeCompletePipeline()
    assert await _run_one(
        bootstrap=bootstrap,
        mongo_client=mongo_client,
        pipeline=pipeline2,
        group_id=group_id,
        partition=partition2,
        start_offset=offset2,
    ) == 1
    assert pipeline2.calls == 0

    db = mongo_client.get_default_database()
    assert db is not None
    count = await db[MEMORY_EXTRACTION_TASK_COLLECTION].count_documents(
        {"archive_id": event.archive_id}
    )
    assert count == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_new_event_id_same_archive_id_single_task(
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: AIOKafkaProducer,
    mongo_kafka_stack: tuple[str, str],
) -> None:
    _, bootstrap = mongo_kafka_stack
    event1 = _new_event()
    group_id = _unique_group()

    partition1, offset1 = await _publish_event(kafka_producer, event1)
    assert await _run_one(
        bootstrap=bootstrap,
        mongo_client=mongo_client,
        pipeline=FakeCompletePipeline(),
        group_id=group_id,
        partition=partition1,
        start_offset=offset1,
    ) == 1

    event2 = _new_event(
        archive_id=event1.archive_id,
        user_id=event1.user_id,
        session_id=event1.session_id,
    )
    pipeline2 = FakeCompletePipeline()
    partition2, offset2 = await _publish_event(kafka_producer, event2)
    assert await _run_one(
        bootstrap=bootstrap,
        mongo_client=mongo_client,
        pipeline=pipeline2,
        group_id=group_id,
        partition=partition2,
        start_offset=offset2,
    ) == 1
    assert pipeline2.calls == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_crash_replay_abort_then_complete_increments_attempt(
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: AIOKafkaProducer,
    mongo_kafka_stack: tuple[str, str],
) -> None:
    _, bootstrap = mongo_kafka_stack
    event = _new_event()
    group_id = _unique_group()
    pipeline = FakeAbortThenComplete()

    partition, offset = await _publish_event(kafka_producer, event)

    assert await _run_one(
        bootstrap=bootstrap,
        mongo_client=mongo_client,
        pipeline=pipeline,
        group_id=group_id,
        partition=partition,
        start_offset=offset,
    ) == 1

    task_mid = await find_extraction_task_by_archive_id(mongo_client, event.archive_id)
    assert task_mid is not None
    assert task_mid.status == ExtractionTaskStatus.PROCESSING
    assert task_mid.attempt_count >= 1

    assert await _run_one(
        bootstrap=bootstrap,
        mongo_client=mongo_client,
        pipeline=pipeline,
        group_id=group_id,
        partition=partition,
        start_offset=offset,
    ) == 1

    task_done = await find_extraction_task_by_archive_id(mongo_client, event.archive_id)
    assert task_done is not None
    assert task_done.status == ExtractionTaskStatus.COMPLETED
    assert task_done.attempt_count >= 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_db_failure_before_commit_allows_replay(
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: AIOKafkaProducer,
    mongo_kafka_stack: tuple[str, str],
) -> None:
    _, bootstrap = mongo_kafka_stack
    event = _new_event()
    group_id = _unique_group()
    partition, offset = await _publish_event(kafka_producer, event)

    with patch.object(
        repo,
        "mark_completed",
        side_effect=RuntimeError("injected terminal write failure"),
    ):
        with pytest.raises(TerminalPersistError):
            await _run_one(
                bootstrap=bootstrap,
                mongo_client=mongo_client,
                pipeline=FakeCompletePipeline(),
                group_id=group_id,
                partition=partition,
                start_offset=offset,
            )

    committed = await _committed_offset(
        bootstrap,
        group_id=group_id,
        topic=TOPIC,
        partition=partition,
    )
    assert committed is None or committed <= offset

    assert await _run_one(
        bootstrap=bootstrap,
        mongo_client=mongo_client,
        pipeline=FakeCompletePipeline(),
        group_id=group_id,
        partition=partition,
        start_offset=offset,
    ) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_malformed_extra_key_no_task_no_commit(
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: AIOKafkaProducer,
    mongo_kafka_stack: tuple[str, str],
) -> None:
    _, bootstrap = mongo_kafka_stack
    event = _new_event()
    group_id = _unique_group()
    payload = json.loads(event.to_json_bytes().decode("utf-8"))
    payload["unexpected"] = "x"
    bad_value = json.dumps(payload).encode("utf-8")
    partition, offset = await _publish_event(
        kafka_producer,
        event,
        value=bad_value,
    )

    with pytest.raises(MalformedArchiveCreatedEventError):
        await _run_one(
            bootstrap=bootstrap,
            mongo_client=mongo_client,
            pipeline=FakeCompletePipeline(),
            group_id=group_id,
            partition=partition,
            start_offset=offset,
        )

    assert await find_extraction_task_by_archive_id(mongo_client, event.archive_id) is None
    committed = await _committed_offset(
        bootstrap,
        group_id=group_id,
        topic=TOPIC,
        partition=partition,
    )
    assert committed is None or committed <= offset


@pytest.mark.integration
@pytest.mark.asyncio
async def test_key_mismatch_no_task_no_commit_stops(
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: AIOKafkaProducer,
    mongo_kafka_stack: tuple[str, str],
) -> None:
    _, bootstrap = mongo_kafka_stack
    event = _new_event()
    group_id = _unique_group()
    partition, offset = await _publish_event(
        kafka_producer,
        event,
        key=b"wrong-user-key",
    )

    with pytest.raises(ArchiveCreatedKeyMismatchError):
        await _run_one(
            bootstrap=bootstrap,
            mongo_client=mongo_client,
            pipeline=FakeCompletePipeline(),
            group_id=group_id,
            partition=partition,
            start_offset=offset,
        )

    assert await find_extraction_task_by_archive_id(mongo_client, event.archive_id) is None
    committed = await _committed_offset(
        bootstrap,
        group_id=group_id,
        topic=TOPIC,
        partition=partition,
    )
    assert committed is None or committed <= offset


@pytest.mark.integration
@pytest.mark.asyncio
async def test_failed_terminal_commits_offset(
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: AIOKafkaProducer,
    mongo_kafka_stack: tuple[str, str],
) -> None:
    _, bootstrap = mongo_kafka_stack
    event = _new_event()
    group_id = _unique_group()
    partition, offset = await _publish_event(kafka_producer, event)

    assert await _run_one(
        bootstrap=bootstrap,
        mongo_client=mongo_client,
        pipeline=FakeFailPipeline(),
        group_id=group_id,
        partition=partition,
        start_offset=offset,
    ) == 1

    task = await find_extraction_task_by_archive_id(mongo_client, event.archive_id)
    assert task is not None
    assert task.status == ExtractionTaskStatus.FAILED
    assert task.last_error is not None

    committed = await _committed_offset(
        bootstrap,
        group_id=group_id,
        topic=TOPIC,
        partition=partition,
    )
    assert committed == offset + 1
