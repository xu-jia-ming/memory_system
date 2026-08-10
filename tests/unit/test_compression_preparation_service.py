"""Unit tests for compression preparation domain service orchestration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from memory_system.domain.enums.compression_preparation import CompressionPreparationStatus
from memory_system.domain.models.compression_preparation import CompressionPreparationInput
from memory_system.domain.services.compression_preparation_service import (
    CompressionPreparationValidationError,
    prepare_pending_archive_and_publish,
)

USER_ID = "user_001"
SESSION_ID = "session_001"
ARCHIVE_ID = "arch-001"
BATCH_KEY = "session_001:m1:m2"
TOKEN = "lock-token-001"
TOPIC = "context.archive.created"
TTL = 420
FIXED_NOW = 1_700_000_000


def _input(**overrides: object) -> CompressionPreparationInput:
    data: dict[str, object] = {
        "user_id": USER_ID,
        "session_id": SESSION_ID,
        "archive_id": ARCHIVE_ID,
        "archive_batch_key": BATCH_KEY,
        "pending_archive_message_count": 3,
        "pending_archive_estimated_tokens": 100,
        "lock_owner_token": None,
    }
    data.update(overrides)
    return CompressionPreparationInput.model_validate(data)


@pytest.mark.asyncio
async def test_empty_archive_id_raises_validation_error_before_redis() -> None:
    mock_redis = MagicMock()
    mock_producer = MagicMock()
    with pytest.raises((CompressionPreparationValidationError, ValidationError)):
        await prepare_pending_archive_and_publish(
            redis=mock_redis,
            kafka_producer=mock_producer,
            topic=TOPIC,
            input=_input(archive_id="   "),
            lock_ttl_seconds=TTL,
        )


@pytest.mark.asyncio
async def test_count_zero_rejected_by_model_or_service() -> None:
    with pytest.raises((CompressionPreparationValidationError, ValidationError)):
        CompressionPreparationInput(
            user_id=USER_ID,
            session_id=SESSION_ID,
            archive_id=ARCHIVE_ID,
            archive_batch_key=BATCH_KEY,
            pending_archive_message_count=0,
            pending_archive_estimated_tokens=10,
        )


@pytest.mark.asyncio
async def test_empty_lock_token_string_raises() -> None:
    with pytest.raises((CompressionPreparationValidationError, ValidationError)):
        await prepare_pending_archive_and_publish(
            redis=MagicMock(),
            kafka_producer=MagicMock(),
            topic=TOPIC,
            input=_input(lock_owner_token=""),
            lock_ttl_seconds=TTL,
        )


@pytest.mark.asyncio
async def test_fresh_lock_failure_zero_side_effect() -> None:
    mock_redis = MagicMock()
    mock_producer = MagicMock()
    mock_producer.send_and_wait = AsyncMock()

    with (
        patch(
            "memory_system.domain.services.compression_preparation_service.acquire_compression_lock",
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_acquire,
        patch(
            "memory_system.domain.services.compression_preparation_service.execute_pending_archive_write_lua",
            new_callable=AsyncMock,
        ) as mock_lua,
        patch(
            "memory_system.domain.services.compression_preparation_service.publish_archive_created_event",
            new_callable=AsyncMock,
        ) as mock_publish,
    ):
        result = await prepare_pending_archive_and_publish(
            redis=mock_redis,
            kafka_producer=mock_producer,
            topic=TOPIC,
            input=_input(),
            lock_ttl_seconds=TTL,
        )

    assert result.status == CompressionPreparationStatus.LOCK_NOT_ACQUIRED
    mock_acquire.assert_awaited_once()
    mock_lua.assert_not_awaited()
    mock_publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_valid_fresh_lock_success_path() -> None:
    mock_redis = MagicMock()
    mock_producer = MagicMock()

    with (
        patch(
            "memory_system.domain.services.compression_preparation_service.acquire_compression_lock",
            new_callable=AsyncMock,
            return_value=TOKEN,
        ),
        patch(
            "memory_system.domain.services.compression_preparation_service.execute_pending_archive_write_lua",
            new_callable=AsyncMock,
            return_value=CompressionPreparationStatus.SUCCESS,
        ) as mock_lua,
        patch(
            "memory_system.domain.services.compression_preparation_service.publish_archive_created_event",
            new_callable=AsyncMock,
        ) as mock_publish,
        patch(
            "memory_system.domain.services.compression_preparation_service.release_compression_lock",
            new_callable=AsyncMock,
        ) as mock_release,
    ):
        result = await prepare_pending_archive_and_publish(
            redis=mock_redis,
            kafka_producer=mock_producer,
            topic=TOPIC,
            input=_input(),
            lock_ttl_seconds=TTL,
            clock=lambda: FIXED_NOW,
        )

    assert result.status == CompressionPreparationStatus.SUCCESS
    assert result.lock_owner_token == TOKEN
    assert result.event_id is not None
    mock_lua.assert_awaited_once()
    assert mock_lua.await_args is not None
    assert mock_lua.await_args.kwargs["expected_lock_owner_token"] == TOKEN
    mock_publish.assert_awaited_once()
    mock_release.assert_not_awaited()


@pytest.mark.asyncio
async def test_valid_preheld_skips_acquire_uses_lua() -> None:
    mock_redis = MagicMock()

    with (
        patch(
            "memory_system.domain.services.compression_preparation_service.acquire_compression_lock",
            new_callable=AsyncMock,
        ) as mock_acquire,
        patch(
            "memory_system.domain.services.compression_preparation_service.execute_pending_archive_write_lua",
            new_callable=AsyncMock,
            return_value=CompressionPreparationStatus.SUCCESS,
        ) as mock_lua,
        patch(
            "memory_system.domain.services.compression_preparation_service.publish_archive_created_event",
            new_callable=AsyncMock,
        ),
    ):
        result = await prepare_pending_archive_and_publish(
            redis=mock_redis,
            kafka_producer=MagicMock(),
            topic=TOPIC,
            input=_input(lock_owner_token=TOKEN),
            lock_ttl_seconds=TTL,
            clock=lambda: FIXED_NOW,
        )

    assert result.status == CompressionPreparationStatus.SUCCESS
    mock_acquire.assert_not_awaited()
    assert mock_lua.await_args is not None
    assert mock_lua.await_args.kwargs["expected_lock_owner_token"] == TOKEN


@pytest.mark.asyncio
async def test_stale_preheld_lock_not_acquired_no_publish() -> None:
    with (
        patch(
            "memory_system.domain.services.compression_preparation_service.execute_pending_archive_write_lua",
            new_callable=AsyncMock,
            return_value=CompressionPreparationStatus.LOCK_NOT_ACQUIRED,
        ),
        patch(
            "memory_system.domain.services.compression_preparation_service.publish_archive_created_event",
            new_callable=AsyncMock,
        ) as mock_publish,
        patch(
            "memory_system.domain.services.compression_preparation_service.release_compression_lock",
            new_callable=AsyncMock,
        ) as mock_release,
    ):
        result = await prepare_pending_archive_and_publish(
            redis=MagicMock(),
            kafka_producer=MagicMock(),
            topic=TOPIC,
            input=_input(lock_owner_token="stale-token"),
            lock_ttl_seconds=TTL,
        )

    assert result.status == CompressionPreparationStatus.LOCK_NOT_ACQUIRED
    assert result.lock_owner_token is None
    mock_publish.assert_not_awaited()
    mock_release.assert_not_awaited()


@pytest.mark.asyncio
async def test_expired_preheld_same_as_stale() -> None:
    with (
        patch(
            "memory_system.domain.services.compression_preparation_service.execute_pending_archive_write_lua",
            new_callable=AsyncMock,
            return_value=CompressionPreparationStatus.LOCK_NOT_ACQUIRED,
        ),
        patch(
            "memory_system.domain.services.compression_preparation_service.publish_archive_created_event",
            new_callable=AsyncMock,
        ) as mock_publish,
    ):
        result = await prepare_pending_archive_and_publish(
            redis=MagicMock(),
            kafka_producer=MagicMock(),
            topic=TOPIC,
            input=_input(lock_owner_token="expired-token"),
            lock_ttl_seconds=TTL,
        )

    assert result.status == CompressionPreparationStatus.LOCK_NOT_ACQUIRED
    mock_publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_publish_failure_keeps_pending_and_lock() -> None:
    with (
        patch(
            "memory_system.domain.services.compression_preparation_service.acquire_compression_lock",
            new_callable=AsyncMock,
            return_value=TOKEN,
        ),
        patch(
            "memory_system.domain.services.compression_preparation_service.execute_pending_archive_write_lua",
            new_callable=AsyncMock,
            return_value=CompressionPreparationStatus.SUCCESS,
        ),
        patch(
            "memory_system.domain.services.compression_preparation_service.publish_archive_created_event",
            new_callable=AsyncMock,
            side_effect=RuntimeError("broker down"),
        ),
        patch(
            "memory_system.domain.services.compression_preparation_service.release_compression_lock",
            new_callable=AsyncMock,
        ) as mock_release,
    ):
        result = await prepare_pending_archive_and_publish(
            redis=MagicMock(),
            kafka_producer=MagicMock(),
            topic=TOPIC,
            input=_input(),
            lock_ttl_seconds=TTL,
            clock=lambda: FIXED_NOW,
        )

    assert result.status == CompressionPreparationStatus.PUBLISH_FAILED
    assert result.lock_owner_token == TOKEN
    assert result.event_id is None
    mock_release.assert_not_awaited()


@pytest.mark.asyncio
async def test_pending_conflict_releases_fresh_lock_no_publish() -> None:
    with (
        patch(
            "memory_system.domain.services.compression_preparation_service.acquire_compression_lock",
            new_callable=AsyncMock,
            return_value=TOKEN,
        ),
        patch(
            "memory_system.domain.services.compression_preparation_service.execute_pending_archive_write_lua",
            new_callable=AsyncMock,
            return_value=CompressionPreparationStatus.PENDING_CONFLICT,
        ),
        patch(
            "memory_system.domain.services.compression_preparation_service.publish_archive_created_event",
            new_callable=AsyncMock,
        ) as mock_publish,
        patch(
            "memory_system.domain.services.compression_preparation_service.release_compression_lock",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_release,
    ):
        result = await prepare_pending_archive_and_publish(
            redis=MagicMock(),
            kafka_producer=MagicMock(),
            topic=TOPIC,
            input=_input(),
            lock_ttl_seconds=TTL,
        )

    assert result.status == CompressionPreparationStatus.PENDING_CONFLICT
    mock_publish.assert_not_awaited()
    mock_release.assert_awaited_once()


@pytest.mark.asyncio
async def test_idempotent_retry_republishes() -> None:
    with (
        patch(
            "memory_system.domain.services.compression_preparation_service.execute_pending_archive_write_lua",
            new_callable=AsyncMock,
            return_value=CompressionPreparationStatus.SUCCESS,
        ),
        patch(
            "memory_system.domain.services.compression_preparation_service.publish_archive_created_event",
            new_callable=AsyncMock,
        ) as mock_publish,
    ):
        result = await prepare_pending_archive_and_publish(
            redis=MagicMock(),
            kafka_producer=MagicMock(),
            topic=TOPIC,
            input=_input(lock_owner_token=TOKEN),
            lock_ttl_seconds=TTL,
            clock=lambda: FIXED_NOW,
        )

    assert result.status == CompressionPreparationStatus.SUCCESS
    mock_publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_invalid_session_state_no_publish() -> None:
    with (
        patch(
            "memory_system.domain.services.compression_preparation_service.execute_pending_archive_write_lua",
            new_callable=AsyncMock,
            return_value=CompressionPreparationStatus.INVALID_SESSION_STATE,
        ),
        patch(
            "memory_system.domain.services.compression_preparation_service.publish_archive_created_event",
            new_callable=AsyncMock,
        ) as mock_publish,
    ):
        result = await prepare_pending_archive_and_publish(
            redis=MagicMock(),
            kafka_producer=MagicMock(),
            topic=TOPIC,
            input=_input(lock_owner_token=TOKEN),
            lock_ttl_seconds=TTL,
        )

    assert result.status == CompressionPreparationStatus.INVALID_SESSION_STATE
    mock_publish.assert_not_awaited()
