"""MongoDB repository for memory_extraction_task (§2.1.3 / §2.1.4)."""

from __future__ import annotations

import uuid
from typing import Any

from pymongo import AsyncMongoClient, ReturnDocument
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.domain.models.extraction_task import ExtractionLastError, MemoryExtractionTask

MEMORY_EXTRACTION_TASK_COLLECTION = "memory_extraction_task"


def _get_database(mongodb: AsyncMongoClient[Any]) -> AsyncDatabase[Any]:
    db = mongodb.get_default_database()
    if db is None:
        raise RuntimeError(
            "MongoDB URI must include a default database path "
            "(e.g. mongodb://host:27017/memory_system)"
        )
    return db


def _collection(mongodb: AsyncMongoClient[Any]) -> AsyncCollection[Any]:
    return _get_database(mongodb)[MEMORY_EXTRACTION_TASK_COLLECTION]


def extraction_task_from_document(document: dict[str, Any]) -> MemoryExtractionTask:
    """Map Mongo document to MemoryExtractionTask (fail-closed on missing fields)."""
    required = (
        "task_id",
        "archive_id",
        "user_id",
        "status",
        "attempt_count",
        "created_time",
        "updated_time",
    )
    for field in required:
        if field not in document:
            raise ValueError(f"missing required extraction task field: {field}")

    raw_last_error = document.get("last_error")
    last_error: ExtractionLastError | None
    if raw_last_error is None:
        last_error = None
    elif isinstance(raw_last_error, dict):
        last_error = ExtractionLastError(
            error_code=str(raw_last_error["error_code"]),
            failed_stage=str(raw_last_error["failed_stage"]),
            message=str(raw_last_error["message"]),
        )
    else:
        raise ValueError("last_error must be a BSON document or null")

    raw_result = document.get("extraction_result")
    if raw_result is not None and not isinstance(raw_result, dict):
        raise ValueError("extraction_result must be a BSON document or null")

    completed_time = document.get("completed_time")
    if completed_time is not None:
        completed_time = int(completed_time)

    return MemoryExtractionTask(
        task_id=str(document["task_id"]),
        archive_id=str(document["archive_id"]),
        user_id=str(document["user_id"]),
        status=ExtractionTaskStatus(str(document["status"])),
        attempt_count=int(document["attempt_count"]),
        extraction_result=raw_result,
        last_error=last_error,
        created_time=int(document["created_time"]),
        updated_time=int(document["updated_time"]),
        completed_time=completed_time,
    )


async def find_extraction_task_by_archive_id(
    mongodb: AsyncMongoClient[Any],
    archive_id: str,
) -> MemoryExtractionTask | None:
    """Find extraction task by archive_id (unique index)."""
    document = await _collection(mongodb).find_one({"archive_id": archive_id})
    if document is None:
        return None
    return extraction_task_from_document(document)


async def find_extraction_task_by_user_and_archive_id(
    mongodb: AsyncMongoClient[Any],
    user_id: str,
    archive_id: str,
) -> MemoryExtractionTask | None:
    """Find extraction task by user_id + archive_id (cross-user isolation)."""
    document = await _collection(mongodb).find_one(
        {"user_id": user_id, "archive_id": archive_id}
    )
    if document is None:
        return None
    return extraction_task_from_document(document)


async def upsert_pending_extraction_task(
    mongodb: AsyncMongoClient[Any],
    *,
    archive_id: str,
    user_id: str,
    now: int,
) -> MemoryExtractionTask:
    """Upsert pending task via ``$setOnInsert``; never overwrite existing status.

    Concurrent insert races: capture DuplicateKeyError and reload existing.
    """
    task_id = str(uuid.uuid4())
    on_insert: dict[str, Any] = {
        "task_id": task_id,
        "archive_id": archive_id,
        "user_id": user_id,
        "status": ExtractionTaskStatus.PENDING.value,
        "attempt_count": 0,
        "extraction_result": None,
        "last_error": None,
        "created_time": now,
        "updated_time": now,
        "completed_time": None,
    }
    try:
        await _collection(mongodb).update_one(
            {"archive_id": archive_id},
            {"$setOnInsert": on_insert},
            upsert=True,
        )
    except DuplicateKeyError:
        pass

    task = await find_extraction_task_by_archive_id(mongodb, archive_id)
    if task is None:
        raise RuntimeError(f"extraction task missing after upsert archive_id={archive_id}")
    return task


async def mark_processing_from_pending(
    mongodb: AsyncMongoClient[Any],
    *,
    archive_id: str,
    now: int,
) -> MemoryExtractionTask | None:
    """Transition pending → processing; attempt_count += 1; clear last_error."""
    document = await _collection(mongodb).find_one_and_update(
        {
            "archive_id": archive_id,
            "status": ExtractionTaskStatus.PENDING.value,
        },
        {
            "$set": {
                "status": ExtractionTaskStatus.PROCESSING.value,
                "last_error": None,
                "updated_time": now,
            },
            "$inc": {"attempt_count": 1},
        },
        return_document=ReturnDocument.AFTER,
    )
    if document is None:
        return None
    return extraction_task_from_document(document)


async def bump_processing_attempt(
    mongodb: AsyncMongoClient[Any],
    *,
    archive_id: str,
    now: int,
) -> MemoryExtractionTask | None:
    """Bump attempt_count for an existing processing task (crash replay)."""
    document = await _collection(mongodb).find_one_and_update(
        {
            "archive_id": archive_id,
            "status": ExtractionTaskStatus.PROCESSING.value,
        },
        {
            "$set": {"updated_time": now},
            "$inc": {"attempt_count": 1},
        },
        return_document=ReturnDocument.AFTER,
    )
    if document is None:
        return None
    return extraction_task_from_document(document)


async def mark_completed(
    mongodb: AsyncMongoClient[Any],
    *,
    archive_id: str,
    now: int,
) -> MemoryExtractionTask:
    """Persist terminal completed status; raises if write does not apply."""
    document = await _collection(mongodb).find_one_and_update(
        {
            "archive_id": archive_id,
            "status": ExtractionTaskStatus.PROCESSING.value,
        },
        {
            "$set": {
                "status": ExtractionTaskStatus.COMPLETED.value,
                "last_error": None,
                "updated_time": now,
                "completed_time": now,
            },
        },
        return_document=ReturnDocument.AFTER,
    )
    if document is None:
        raise RuntimeError(
            f"failed to mark extraction task completed archive_id={archive_id}"
        )
    return extraction_task_from_document(document)


async def set_extraction_result(
    mongodb: AsyncMongoClient[Any],
    *,
    archive_id: str,
    extraction_result: dict[str, Any],
    now: int,
) -> MemoryExtractionTask | None:
    """Persist validated extraction_result for a processing task only."""
    document = await _collection(mongodb).find_one_and_update(
        {
            "archive_id": archive_id,
            "status": ExtractionTaskStatus.PROCESSING.value,
        },
        {
            "$set": {
                "extraction_result": extraction_result,
                "updated_time": now,
            },
        },
        return_document=ReturnDocument.AFTER,
    )
    if document is None:
        return None
    return extraction_task_from_document(document)


async def mark_failed(
    mongodb: AsyncMongoClient[Any],
    *,
    archive_id: str,
    last_error: ExtractionLastError,
    now: int,
) -> MemoryExtractionTask:
    """Persist terminal failed + last_error; preserve extraction_result."""
    document = await _collection(mongodb).find_one_and_update(
        {
            "archive_id": archive_id,
            "status": ExtractionTaskStatus.PROCESSING.value,
        },
        {
            "$set": {
                "status": ExtractionTaskStatus.FAILED.value,
                "last_error": last_error.model_dump(mode="json"),
                "updated_time": now,
            },
        },
        return_document=ReturnDocument.AFTER,
    )
    if document is None:
        raise RuntimeError(f"failed to mark extraction task failed archive_id={archive_id}")
    return extraction_task_from_document(document)


async def admin_reset_failed_to_pending(
    mongodb: AsyncMongoClient[Any],
    *,
    user_id: str,
    archive_id: str,
    now: int,
    clear_extraction_result: bool,
) -> MemoryExtractionTask | None:
    """Admin: failed → pending; clear last_error; optionally clear extraction_result."""
    set_fields: dict[str, Any] = {
        "status": ExtractionTaskStatus.PENDING.value,
        "last_error": None,
        "updated_time": now,
    }
    if clear_extraction_result:
        set_fields["extraction_result"] = None

    document = await _collection(mongodb).find_one_and_update(
        {
            "user_id": user_id,
            "archive_id": archive_id,
            "status": ExtractionTaskStatus.FAILED.value,
        },
        {"$set": set_fields},
        return_document=ReturnDocument.AFTER,
    )
    if document is None:
        return None
    return extraction_task_from_document(document)


async def admin_mark_failed_from_admin_action(
    mongodb: AsyncMongoClient[Any],
    *,
    user_id: str,
    archive_id: str,
    last_error: ExtractionLastError,
    now: int,
) -> MemoryExtractionTask:
    """Admin: mark failed from pending or failed after Kafka publish failure."""
    document = await _collection(mongodb).find_one_and_update(
        {
            "user_id": user_id,
            "archive_id": archive_id,
            "status": {
                "$in": [
                    ExtractionTaskStatus.PENDING.value,
                    ExtractionTaskStatus.FAILED.value,
                ]
            },
        },
        {
            "$set": {
                "status": ExtractionTaskStatus.FAILED.value,
                "last_error": last_error.model_dump(mode="json"),
                "updated_time": now,
            },
        },
        return_document=ReturnDocument.AFTER,
    )
    if document is None:
        raise RuntimeError(
            f"failed to mark extraction task failed from admin action "
            f"user_id={user_id} archive_id={archive_id}"
        )
    return extraction_task_from_document(document)
