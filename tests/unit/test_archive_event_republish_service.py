"""Unit tests for archive event republish domain service."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from memory_system.domain.enums.archive_event_republish import ArchiveEventRepublishStatus
from memory_system.domain.enums.working_memory import MessageRole
from memory_system.domain.models.archive_created_event import ARCHIVE_CREATED_EVENT_FIELD_NAMES
from memory_system.domain.models.archive_event_republish import ArchiveEventRepublishInput
from memory_system.domain.models.context_archive import ContextArchive, ContextArchiveMessage
from memory_system.domain.services.archive_event_republish_service import (
    republish_archive_created_event,
)

ARCHIVE_ID = "00000000-0000-4000-8000-000000000001"
USER_ID = "user_001"
SESSION_ID = "session_001"
TOPIC = "context.archive.created"
FIXED_NOW = 1_700_000_000


def _archive(*, user_id: str = USER_ID, created_time: int = FIXED_NOW) -> ContextArchive:
    return ContextArchive(
        archive_id=ARCHIVE_ID,
        user_id=user_id,
        session_id=SESSION_ID,
        archive_batch_key=f"{SESSION_ID}:m1:m2",
        base_compression_version=0,
        messages=[
            ContextArchiveMessage(
                message_id="m1",
                role=MessageRole.USER,
                content="hello",
                timestamp=FIXED_NOW,
            ),
        ],
        created_time=created_time,
    )


def _input(**overrides: object) -> ArchiveEventRepublishInput:
    data: dict[str, object] = {
        "archive_id": ARCHIVE_ID,
        "expected_user_id": None,
    }
    data.update(overrides)
    return ArchiveEventRepublishInput.model_validate(data)


@pytest.mark.asyncio
async def test_u1_empty_archive_id_returns_invalid_input() -> None:
    mock_mongo = MagicMock()
    mock_producer = MagicMock()
    result = await republish_archive_created_event(
        mongodb=mock_mongo,
        kafka_producer=mock_producer,
        topic=TOPIC,
        input=_input(archive_id="   "),
    )
    assert result.status == ArchiveEventRepublishStatus.INVALID_INPUT
    assert result.event_id is None


@pytest.mark.asyncio
async def test_u3_archive_not_found() -> None:
    mock_mongo = MagicMock()
    mock_producer = MagicMock()
    mock_producer.send_and_wait = AsyncMock()

    with patch(
        "memory_system.domain.services.archive_event_republish_service.find_context_archive_by_id",
        new_callable=AsyncMock,
        return_value=None,
    ) as mock_find:
        result = await republish_archive_created_event(
            mongodb=mock_mongo,
            kafka_producer=mock_producer,
            topic=TOPIC,
            input=_input(),
        )

    assert result.status == ArchiveEventRepublishStatus.ARCHIVE_NOT_FOUND
    mock_find.assert_awaited_once_with(mock_mongo, ARCHIVE_ID)
    mock_producer.send_and_wait.assert_not_awaited()


@pytest.mark.asyncio
async def test_u4_ownership_mismatch() -> None:
    mock_mongo = MagicMock()
    mock_producer = MagicMock()
    mock_producer.send_and_wait = AsyncMock()

    with patch(
        "memory_system.domain.services.archive_event_republish_service.find_context_archive_by_id",
        new_callable=AsyncMock,
        return_value=_archive(),
    ):
        result = await republish_archive_created_event(
            mongodb=mock_mongo,
            kafka_producer=mock_producer,
            topic=TOPIC,
            input=_input(expected_user_id="other_user"),
        )

    assert result.status == ArchiveEventRepublishStatus.ARCHIVE_OWNERSHIP_MISMATCH
    mock_producer.send_and_wait.assert_not_awaited()


@pytest.mark.asyncio
async def test_u5_invalid_archive_document() -> None:
    mock_mongo = MagicMock()
    mock_producer = MagicMock()
    mock_producer.send_and_wait = AsyncMock()

    with patch(
        "memory_system.domain.services.archive_event_republish_service.find_context_archive_by_id",
        new_callable=AsyncMock,
        side_effect=ValueError("missing required archive field: session_id"),
    ):
        result = await republish_archive_created_event(
            mongodb=mock_mongo,
            kafka_producer=mock_producer,
            topic=TOPIC,
            input=_input(),
        )

    assert result.status == ArchiveEventRepublishStatus.INVALID_ARCHIVE
    mock_producer.send_and_wait.assert_not_awaited()


@pytest.mark.asyncio
async def test_u6_success_path() -> None:
    mock_mongo = MagicMock()
    mock_producer = MagicMock()
    mock_producer.send_and_wait = AsyncMock(return_value=None)

    with patch(
        "memory_system.domain.services.archive_event_republish_service.find_context_archive_by_id",
        new_callable=AsyncMock,
        return_value=_archive(),
    ):
        result = await republish_archive_created_event(
            mongodb=mock_mongo,
            kafka_producer=mock_producer,
            topic=TOPIC,
            input=_input(),
        )

    assert result.status == ArchiveEventRepublishStatus.SUCCESS
    assert result.event_id is not None
    mock_producer.send_and_wait.assert_awaited_once()


@pytest.mark.asyncio
async def test_u7_payload_exactly_six_fields_and_key() -> None:
    mock_mongo = MagicMock()
    mock_producer = MagicMock()
    mock_producer.send_and_wait = AsyncMock(return_value=None)

    with patch(
        "memory_system.domain.services.archive_event_republish_service.find_context_archive_by_id",
        new_callable=AsyncMock,
        return_value=_archive(),
    ):
        await republish_archive_created_event(
            mongodb=mock_mongo,
            kafka_producer=mock_producer,
            topic=TOPIC,
            input=_input(),
        )

    args, kwargs = mock_producer.send_and_wait.await_args
    assert args[0] == TOPIC
    assert kwargs["key"] == USER_ID.encode("utf-8")
    payload = json.loads(kwargs["value"].decode("utf-8"))
    assert set(payload.keys()) == set(ARCHIVE_CREATED_EVENT_FIELD_NAMES)
    assert "base_compression_version" not in payload
    assert "archive_batch_key" not in payload


@pytest.mark.asyncio
async def test_u8_created_time_from_archive() -> None:
    archive_time = FIXED_NOW + 42
    mock_mongo = MagicMock()
    mock_producer = MagicMock()
    mock_producer.send_and_wait = AsyncMock(return_value=None)

    with patch(
        "memory_system.domain.services.archive_event_republish_service.find_context_archive_by_id",
        new_callable=AsyncMock,
        return_value=_archive(created_time=archive_time),
    ):
        await republish_archive_created_event(
            mongodb=mock_mongo,
            kafka_producer=mock_producer,
            topic=TOPIC,
            input=_input(),
        )

    args, kwargs = mock_producer.send_and_wait.await_args
    payload = json.loads(kwargs["value"].decode("utf-8"))
    assert payload["created_time"] == archive_time


@pytest.mark.asyncio
async def test_u9_kafka_publish_failure() -> None:
    mock_mongo = MagicMock()
    mock_producer = MagicMock()
    mock_producer.send_and_wait = AsyncMock(side_effect=RuntimeError("broker down"))

    with patch(
        "memory_system.domain.services.archive_event_republish_service.find_context_archive_by_id",
        new_callable=AsyncMock,
        return_value=_archive(),
    ):
        result = await republish_archive_created_event(
            mongodb=mock_mongo,
            kafka_producer=mock_producer,
            topic=TOPIC,
            input=_input(),
        )

    assert result.status == ArchiveEventRepublishStatus.KAFKA_PUBLISH_FAILED
    assert result.event_id is None


@pytest.mark.asyncio
async def test_u10_duplicate_calls_produce_distinct_event_ids() -> None:
    mock_mongo = MagicMock()
    mock_producer = MagicMock()
    mock_producer.send_and_wait = AsyncMock(return_value=None)

    with patch(
        "memory_system.domain.services.archive_event_republish_service.find_context_archive_by_id",
        new_callable=AsyncMock,
        return_value=_archive(),
    ):
        first = await republish_archive_created_event(
            mongodb=mock_mongo,
            kafka_producer=mock_producer,
            topic=TOPIC,
            input=_input(),
        )
        second = await republish_archive_created_event(
            mongodb=mock_mongo,
            kafka_producer=mock_producer,
            topic=TOPIC,
            input=_input(),
        )

    assert first.status == ArchiveEventRepublishStatus.SUCCESS
    assert second.status == ArchiveEventRepublishStatus.SUCCESS
    assert first.event_id is not None
    assert second.event_id is not None
    assert first.event_id != second.event_id
