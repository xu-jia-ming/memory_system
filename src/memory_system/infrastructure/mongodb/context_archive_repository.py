"""MongoDB repository for context_archive collection (§1.2.2)."""

from __future__ import annotations

from typing import Any

from pymongo import AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from memory_system.domain.enums.working_memory import MessageRole
from memory_system.domain.models.context_archive import ContextArchive, ContextArchiveMessage

CONTEXT_ARCHIVE_COLLECTION = "context_archive"


def _get_database(mongodb: AsyncMongoClient[Any]) -> AsyncDatabase[Any]:
    db = mongodb.get_default_database()
    if db is None:
        raise RuntimeError(
            "MongoDB URI must include a default database path "
            "(e.g. mongodb://host:27017/memory_system)"
        )
    return db


def _collection(mongodb: AsyncMongoClient[Any]) -> AsyncCollection[Any]:
    return _get_database(mongodb)[CONTEXT_ARCHIVE_COLLECTION]


def _message_from_bson(raw: object) -> ContextArchiveMessage:
    if not isinstance(raw, dict):
        raise ValueError("archive message must be a BSON document")
    return ContextArchiveMessage(
        message_id=str(raw["message_id"]),
        role=MessageRole(str(raw["role"])),
        content=str(raw["content"]),
        timestamp=int(raw["timestamp"]),
    )


def context_archive_from_document(document: dict[str, Any]) -> ContextArchive:
    """Map Mongo document to ContextArchive (fail-closed on missing fields)."""
    required = (
        "archive_id",
        "user_id",
        "session_id",
        "archive_batch_key",
        "base_compression_version",
        "messages",
        "created_time",
    )
    for field in required:
        if field not in document:
            raise ValueError(f"missing required archive field: {field}")

    raw_messages = document["messages"]
    if not isinstance(raw_messages, list):
        raise ValueError("archive messages must be a list")

    return ContextArchive(
        archive_id=str(document["archive_id"]),
        user_id=str(document["user_id"]),
        session_id=str(document["session_id"]),
        archive_batch_key=str(document["archive_batch_key"]),
        base_compression_version=int(document["base_compression_version"]),
        messages=[_message_from_bson(msg) for msg in raw_messages],
        created_time=int(document["created_time"]),
    )


async def insert_context_archive(mongodb: AsyncMongoClient[Any], document: dict[str, Any]) -> None:
    """Insert one archive document; DuplicateKeyError propagates to caller."""
    await _collection(mongodb).insert_one(document)


async def find_context_archive_by_batch_key(
    mongodb: AsyncMongoClient[Any],
    archive_batch_key: str,
) -> ContextArchive | None:
    """Find archive by deterministic batch key."""
    document = await _collection(mongodb).find_one({"archive_batch_key": archive_batch_key})
    if document is None:
        return None
    return context_archive_from_document(document)


async def find_context_archive_by_id(
    mongodb: AsyncMongoClient[Any],
    archive_id: str,
) -> ContextArchive | None:
    """Find archive by archive_id (unique index)."""
    document = await _collection(mongodb).find_one({"archive_id": archive_id})
    if document is None:
        return None
    return context_archive_from_document(document)


async def count_by_batch_key(mongodb: AsyncMongoClient[Any], archive_batch_key: str) -> int:
    """Count physical documents for a batch key (integration assertions)."""
    count = await _collection(mongodb).count_documents({"archive_batch_key": archive_batch_key})
    return int(count)


def is_archive_batch_key_duplicate_error(exc: DuplicateKeyError) -> bool:
    """Return True when DuplicateKeyError is on archive_batch_key_unique."""
    details = exc.details or {}
    key_pattern = details.get("keyPattern") or {}
    if "archive_batch_key" in key_pattern:
        return True
    errmsg = str(details.get("errmsg", ""))
    return "archive_batch_key_unique" in errmsg
