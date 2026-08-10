"""Context archive create/reuse domain service (§1.2.2)."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from typing import Any

from pymongo import AsyncMongoClient
from pymongo.errors import DuplicateKeyError

from memory_system.domain.enums.context_archive import ContextArchiveOutcome
from memory_system.domain.models.context_archive import (
    ContextArchive,
    ContextArchiveCreateInput,
    ContextArchiveResult,
    archive_document_from_input,
    archive_messages_from_working_memory,
)
from memory_system.infrastructure.mongodb.context_archive_repository import (
    find_context_archive_by_batch_key,
    insert_context_archive,
    is_archive_batch_key_duplicate_error,
)

Clock = Callable[[], int]


class ContextArchiveValidationError(ValueError):
    """Raised when service-layer input validation fails before Mongo write."""


def _default_clock() -> int:
    return int(time.time())


def build_archive_batch_key(
    session_id: str,
    first_message_id: str,
    last_message_id: str,
) -> str:
    """Deterministic archive batch key: session_id:first_message_id:last_message_id."""
    return f"{session_id}:{first_message_id}:{last_message_id}"


def _validate_input(input: ContextArchiveCreateInput) -> None:
    if not input.user_id.strip():
        raise ContextArchiveValidationError("user_id must not be empty")
    if not input.session_id.strip():
        raise ContextArchiveValidationError("session_id must not be empty")
    if not input.archive_batch_key.strip():
        raise ContextArchiveValidationError("archive_batch_key must not be empty")
    if not input.messages:
        raise ContextArchiveValidationError("messages must not be empty")

    expected_key = build_archive_batch_key(
        input.session_id,
        input.messages[0].message_id,
        input.messages[-1].message_id,
    )
    if input.archive_batch_key != expected_key:
        raise ContextArchiveValidationError(
            f"archive_batch_key {input.archive_batch_key!r} does not match "
            f"expected {expected_key!r}"
        )


def _archive_from_create_input(
    *,
    input: ContextArchiveCreateInput,
    archive_id: str,
    created_time: int,
) -> ContextArchive:
    return ContextArchive(
        archive_id=archive_id,
        user_id=input.user_id,
        session_id=input.session_id,
        archive_batch_key=input.archive_batch_key,
        base_compression_version=input.base_compression_version,
        messages=archive_messages_from_working_memory(input.messages),
        created_time=created_time,
    )


async def create_or_reuse_context_archive(
    *,
    mongodb: AsyncMongoClient[Any],
    input: ContextArchiveCreateInput,
    clock: Clock | None = None,
) -> ContextArchiveResult:
    """Create a new context archive or reuse an existing one by archive_batch_key."""
    _validate_input(input)

    archive_id = str(uuid.uuid4())
    created_time = (clock or _default_clock)()
    document = archive_document_from_input(
        input=input,
        archive_id=archive_id,
        created_time=created_time,
    )

    try:
        await insert_context_archive(mongodb, document)
    except DuplicateKeyError as exc:
        if not is_archive_batch_key_duplicate_error(exc):
            raise
        existing = await find_context_archive_by_batch_key(mongodb, input.archive_batch_key)
        if existing is None:
            raise RuntimeError(
                f"archive_batch_key conflict but no document found for {input.archive_batch_key!r}"
            ) from exc
        return ContextArchiveResult(
            outcome=ContextArchiveOutcome.REUSED,
            archive_id=existing.archive_id,
            archive=existing,
        )

    archive = _archive_from_create_input(
        input=input,
        archive_id=archive_id,
        created_time=created_time,
    )
    return ContextArchiveResult(
        outcome=ContextArchiveOutcome.CREATED,
        archive_id=archive_id,
        archive=archive,
    )
