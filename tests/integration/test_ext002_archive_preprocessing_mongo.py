"""Optional real-Mongo coverage for the EXT-002 raw Archive boundary."""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import patch

import pytest
from pymongo import AsyncMongoClient
from tests.integration.test_extraction_consumer_kafka import (
    _committed_offset,
    _new_event,
    _publish_event,
    _run_one,
    _unique_group,
)

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.domain.services.extraction_archive_preprocessing_service import (
    ExtractionArchivePreprocessingService,
    validate_raw_archive,
)
from memory_system.domain.services.extraction_redaction_service import RedactionFailure
from memory_system.domain.services.extraction_task_consumer_service import TerminalPersistError
from memory_system.infrastructure.mongodb.context_archive_repository import (
    CONTEXT_ARCHIVE_COLLECTION,
    find_context_archive_document_by_id,
)
from memory_system.infrastructure.mongodb.extraction_task_repository import (
    find_extraction_task_by_archive_id,
)

pytest_plugins = ("tests.integration.support.mongo_kafka_fixtures",)


class _FailingRedactor:
    def redact(self, _content: str) -> str:
        raise RedactionFailure("detector failed")


def _document() -> dict[str, Any]:
    return {
        "archive_id": "ext002-integration-archive",
        "user_id": "ext002-integration-user",
        "session_id": "ext002-integration-session",
        "archive_batch_key": "ext002-integration-batch",
        "base_compression_version": 0,
        "messages": [],
        "created_time": 1_700_000_000,
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_raw_lookup_and_strict_validation_do_not_mutate_archive() -> None:
    uri = os.environ.get("EXT002_MONGO_TEST_URI")
    if not uri:
        pytest.skip("EXT002_MONGO_TEST_URI is not configured")
    client: AsyncMongoClient[Any] = AsyncMongoClient(uri)
    try:
        database = client.get_default_database()
        if database is None:
            pytest.skip("EXT002_MONGO_TEST_URI must include a database")
        collection = database[CONTEXT_ARCHIVE_COLLECTION]
        document = _document()
        await collection.delete_many({"archive_id": document["archive_id"]})
        await collection.insert_one(document)
        before = await collection.find_one({"archive_id": document["archive_id"]})

        raw = await find_context_archive_document_by_id(client, document["archive_id"])
        assert raw is not None
        assert validate_raw_archive(raw, document["archive_id"]).messages == []
        assert await collection.find_one({"archive_id": document["archive_id"]}) == before
    finally:
        await client.close()


def _archive_for_event(event: Any) -> dict[str, Any]:
    secret = "sk-abcdefghijklmnopqrstuvwxyz"
    return {
        "archive_id": event.archive_id,
        "user_id": event.user_id,
        "session_id": event.session_id,
        "archive_batch_key": f"batch-{event.archive_id}",
        "base_compression_version": 0,
        "messages": [
            {
                "message_id": "message-1",
                "role": "user",
                "content": f"api-key={secret}",
                "timestamp": 1_700_000_000,
            }
        ],
        "created_time": 1_700_000_000,
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_RED_18_real_pipeline_failure_persists_failed_then_commits_offset(
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: Any,
    mongo_kafka_stack: tuple[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    _, bootstrap = mongo_kafka_stack
    event = _new_event()
    group_id = _unique_group()
    archive = _archive_for_event(event)
    db = mongo_client.get_default_database()
    assert db is not None
    collection = db[CONTEXT_ARCHIVE_COLLECTION]
    await collection.insert_one(archive)
    pipeline = ExtractionArchivePreprocessingService(
        mongo_client,
        redactor=_FailingRedactor(),
    )
    partition, offset = await _publish_event(kafka_producer, event)

    assert await _run_one(
        bootstrap=bootstrap,
        mongo_client=mongo_client,
        pipeline=pipeline,
        group_id=group_id,
        partition=partition,
        start_offset=offset,
    ) == 1

    task = await find_extraction_task_by_archive_id(mongo_client, event.archive_id)
    assert task is not None
    assert task.status == ExtractionTaskStatus.FAILED
    assert task.last_error is not None
    assert task.last_error.error_code == "redaction_failed"
    assert task.last_error.failed_stage == "redaction"
    assert task.last_error.message == "archive redaction failed"
    assert pipeline.last_ready_archive is None
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in caplog.text
    assert await collection.find_one({"archive_id": event.archive_id}) == archive
    assert await _committed_offset(
        bootstrap,
        group_id=group_id,
        topic="context.archive.created",
        partition=partition,
    ) == offset + 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_RED_19_terminal_persistence_failure_leaves_offset_replayable(
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: Any,
    mongo_kafka_stack: tuple[str, str],
) -> None:
    _, bootstrap = mongo_kafka_stack
    event = _new_event()
    group_id = _unique_group()
    db = mongo_client.get_default_database()
    assert db is not None
    await db[CONTEXT_ARCHIVE_COLLECTION].insert_one(_archive_for_event(event))
    pipeline = ExtractionArchivePreprocessingService(
        mongo_client, redactor=_FailingRedactor()
    )
    partition, offset = await _publish_event(kafka_producer, event)

    with patch(
        "memory_system.infrastructure.mongodb.extraction_task_repository.mark_failed",
        side_effect=RuntimeError("injected terminal persistence failure"),
    ):
        with pytest.raises(TerminalPersistError):
            await _run_one(
                bootstrap=bootstrap,
                mongo_client=mongo_client,
                pipeline=pipeline,
                group_id=group_id,
                partition=partition,
                start_offset=offset,
            )

    task_mid = await find_extraction_task_by_archive_id(mongo_client, event.archive_id)
    assert task_mid is not None
    assert task_mid.status == ExtractionTaskStatus.PROCESSING
    assert task_mid.last_error is None
    committed = await _committed_offset(
        bootstrap,
        group_id=group_id,
        topic="context.archive.created",
        partition=partition,
    )
    assert committed is None or committed <= offset
    assert pipeline.last_ready_archive is None

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
    assert task_done.status == ExtractionTaskStatus.FAILED
    assert task_done.last_error is not None
    assert task_done.last_error.error_code == "redaction_failed"
    assert await _committed_offset(
        bootstrap,
        group_id=group_id,
        topic="context.archive.created",
        partition=partition,
    ) == offset + 1
