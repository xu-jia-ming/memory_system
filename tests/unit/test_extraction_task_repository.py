"""Unit tests for extraction_task_repository upsert / status transitions (EXT-001)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pymongo.errors import DuplicateKeyError

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.domain.models.extraction_task import ExtractionLastError
from memory_system.infrastructure.mongodb import extraction_task_repository as repo

NOW = 1_700_000_000


def _pending_doc(**overrides: object) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "task_id": "11111111-1111-4111-8111-111111111111",
        "archive_id": "arch-1",
        "user_id": "user-1",
        "status": "pending",
        "attempt_count": 0,
        "extraction_result": None,
        "last_error": None,
        "created_time": NOW,
        "updated_time": NOW,
        "completed_time": None,
    }
    doc.update(overrides)
    return doc


def _mock_mongodb(collection: MagicMock) -> MagicMock:
    db = MagicMock()
    db.__getitem__.return_value = collection
    client = MagicMock()
    client.get_default_database.return_value = db
    return client


@pytest.mark.asyncio
async def test_upsert_set_on_insert_then_load() -> None:
    collection = MagicMock()
    collection.update_one = AsyncMock(return_value=MagicMock())
    collection.find_one = AsyncMock(return_value=_pending_doc())
    client = _mock_mongodb(collection)

    task = await repo.upsert_pending_extraction_task(
        client, archive_id="arch-1", user_id="user-1", now=NOW
    )
    assert task.status == ExtractionTaskStatus.PENDING
    assert task.attempt_count == 0
    kwargs = collection.update_one.await_args.kwargs
    assert kwargs["upsert"] is True
    assert "$setOnInsert" in collection.update_one.await_args.args[1]
    on_insert = collection.update_one.await_args.args[1]["$setOnInsert"]
    assert on_insert["status"] == "pending"
    assert on_insert["archive_id"] == "arch-1"
    assert "session_id" not in on_insert
    assert "event_id" not in on_insert


@pytest.mark.asyncio
async def test_upsert_duplicate_key_reloads_existing() -> None:
    existing = _pending_doc(status="completed", attempt_count=2, completed_time=NOW)
    collection = MagicMock()
    collection.update_one = AsyncMock(side_effect=DuplicateKeyError("dup"))
    collection.find_one = AsyncMock(return_value=existing)
    client = _mock_mongodb(collection)

    task = await repo.upsert_pending_extraction_task(
        client, archive_id="arch-1", user_id="user-1", now=NOW
    )
    assert task.status == ExtractionTaskStatus.COMPLETED
    assert task.attempt_count == 2


@pytest.mark.asyncio
async def test_mark_processing_from_pending() -> None:
    after = _pending_doc(status="processing", attempt_count=1, last_error=None)
    collection = MagicMock()
    collection.find_one_and_update = AsyncMock(return_value=after)
    client = _mock_mongodb(collection)

    task = await repo.mark_processing_from_pending(client, archive_id="arch-1", now=NOW + 1)
    assert task is not None
    assert task.status == ExtractionTaskStatus.PROCESSING
    assert task.attempt_count == 1
    filt, update = collection.find_one_and_update.await_args.args
    assert filt == {"archive_id": "arch-1", "status": "pending"}
    assert update["$inc"] == {"attempt_count": 1}
    assert update["$set"]["last_error"] is None


@pytest.mark.asyncio
async def test_bump_processing_attempt() -> None:
    after = _pending_doc(status="processing", attempt_count=3, extraction_result={"ok": True})
    collection = MagicMock()
    collection.find_one_and_update = AsyncMock(return_value=after)
    client = _mock_mongodb(collection)

    task = await repo.bump_processing_attempt(client, archive_id="arch-1", now=NOW + 2)
    assert task is not None
    assert task.attempt_count == 3
    assert task.extraction_result == {"ok": True}


@pytest.mark.asyncio
async def test_mark_completed() -> None:
    after = _pending_doc(
        status="completed",
        attempt_count=1,
        completed_time=NOW + 3,
        last_error=None,
    )
    collection = MagicMock()
    collection.find_one_and_update = AsyncMock(return_value=after)
    client = _mock_mongodb(collection)

    task = await repo.mark_completed(client, archive_id="arch-1", now=NOW + 3)
    assert task.status == ExtractionTaskStatus.COMPLETED
    assert task.completed_time == NOW + 3


@pytest.mark.asyncio
async def test_mark_failed_preserves_extraction_result() -> None:
    err = ExtractionLastError(
        error_code="graph_write_failed",
        failed_stage="graph_write",
        message="boom",
    )
    after = _pending_doc(
        status="failed",
        attempt_count=2,
        extraction_result={"candidates": []},
        last_error=err.model_dump(mode="json"),
    )
    collection = MagicMock()
    collection.find_one_and_update = AsyncMock(return_value=after)
    client = _mock_mongodb(collection)

    task = await repo.mark_failed(client, archive_id="arch-1", last_error=err, now=NOW + 4)
    assert task.status == ExtractionTaskStatus.FAILED
    assert task.extraction_result == {"candidates": []}
    assert task.last_error is not None
    assert task.last_error.failed_stage == "graph_write"
    # mark_failed must only $set status/last_error/updated_time — not unset result
    update = collection.find_one_and_update.await_args.args[1]
    assert "extraction_result" not in update["$set"]
    assert "$unset" not in update


@pytest.mark.asyncio
async def test_mark_completed_raises_when_no_document() -> None:
    collection = MagicMock()
    collection.find_one_and_update = AsyncMock(return_value=None)
    client = _mock_mongodb(collection)
    with pytest.raises(RuntimeError, match="completed"):
        await repo.mark_completed(client, archive_id="arch-1", now=NOW)
