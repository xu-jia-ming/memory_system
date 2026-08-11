"""Unit tests for republish_archive_event CLI script."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from scripts.republish_archive_event import _exit_code_for_status, main

from memory_system.domain.enums.archive_event_republish import ArchiveEventRepublishStatus
from memory_system.domain.models.archive_event_republish import ArchiveEventRepublishResult


def test_exit_code_mapping() -> None:
    assert _exit_code_for_status(ArchiveEventRepublishStatus.SUCCESS) == 0
    assert _exit_code_for_status(ArchiveEventRepublishStatus.INVALID_INPUT) == 2
    assert _exit_code_for_status(ArchiveEventRepublishStatus.ARCHIVE_NOT_FOUND) == 1
    assert _exit_code_for_status(ArchiveEventRepublishStatus.KAFKA_PUBLISH_FAILED) == 1


def test_u2_missing_archive_id_exit_2() -> None:
    assert main([]) == 2


def test_u1_whitespace_archive_id_exit_2() -> None:
    assert main(["--archive-id", "   "]) == 2


def test_main_success_exit_0() -> None:
    with (
        patch(
            "scripts.republish_archive_event.get_settings",
            return_value=MagicMock(),
        ),
        patch(
            "scripts.republish_archive_event.asyncio.run",
            return_value=0,
        ) as mock_run,
    ):
        code = main(["--archive-id", "arch-001"])

    assert code == 0
    mock_run.assert_called_once()


def test_main_trims_user_id() -> None:
    async def fake_async_main(
        *,
        archive_id: str,
        expected_user_id: str | None,
        settings: object,
    ) -> int:
        assert archive_id == "arch-001"
        assert expected_user_id == "user_x"
        return 1

    with (
        patch(
            "scripts.republish_archive_event.get_settings",
            return_value=MagicMock(),
        ),
        patch(
            "scripts.republish_archive_event._async_main",
            side_effect=fake_async_main,
        ),
    ):
        code = main(["--archive-id", "arch-001", "--user-id", "  user_x  "])

    assert code == 1


def test_main_maps_service_status_to_exit_code() -> None:
    mock_settings = MagicMock()
    mock_mongo = MagicMock()
    mock_mongo.close = AsyncMock()
    mock_producer = MagicMock()
    mock_producer.start = AsyncMock()
    mock_producer.stop = AsyncMock()

    with (
        patch("scripts.republish_archive_event.get_settings", return_value=mock_settings),
        patch(
            "scripts.republish_archive_event.AsyncMongoClient",
            return_value=mock_mongo,
        ),
        patch(
            "scripts.republish_archive_event._kafka_producer_from_settings",
            return_value=mock_producer,
        ),
        patch(
            "scripts.republish_archive_event.republish_archive_created_event",
            new_callable=AsyncMock,
            return_value=ArchiveEventRepublishResult(
                status=ArchiveEventRepublishStatus.ARCHIVE_NOT_FOUND,
                event_id=None,
            ),
        ),
    ):
        code = main(["--archive-id", "missing-arch"])

    assert code == 1
    mock_producer.start.assert_awaited_once()
    mock_producer.stop.assert_awaited_once()
    mock_mongo.close.assert_awaited_once()


def test_sf4_connection_failure_logs_exclude_secrets(caplog: pytest.LogCaptureFixture) -> None:
    secret_password = "super-secret-mongo-password-xyz"
    mock_settings = MagicMock()
    mock_settings.mongodb.uri.get_secret_value.return_value = (
        f"mongodb://admin:{secret_password}@localhost:27017/memory_system"
    )
    mock_settings.mongodb.server_selection_timeout_ms = 100
    mock_settings.mongodb.connect_timeout_ms = 100
    mock_settings.mongodb.max_pool_size = 1
    mock_settings.kafka.bootstrap_servers = "localhost:9092"
    mock_settings.kafka.topic = "context.archive.created"
    mock_settings.kafka_producer.acks = "all"
    mock_settings.kafka_producer.enable_idempotence = True
    mock_settings.kafka_producer.compression_type = "lz4"
    mock_settings.kafka_producer.request_timeout_ms = 1000
    mock_settings.kafka_producer.max_batch_size = 16384
    mock_settings.kafka_producer.linger_ms = 10

    mock_producer = MagicMock()
    mock_producer.start = AsyncMock(side_effect=ConnectionError("kafka unavailable"))
    mock_producer.stop = AsyncMock()
    mock_mongo = MagicMock()
    mock_mongo.close = AsyncMock()

    with (
        patch("scripts.republish_archive_event.get_settings", return_value=mock_settings),
        patch(
            "scripts.republish_archive_event.AsyncMongoClient",
            return_value=mock_mongo,
        ),
        patch(
            "scripts.republish_archive_event._kafka_producer_from_settings",
            return_value=mock_producer,
        ),
        caplog.at_level(logging.ERROR),
    ):
        code = main(["--archive-id", "arch-001"])

    assert code == 1
    combined_logs = caplog.text
    assert secret_password not in combined_logs
    assert "mongodb://admin:" not in combined_logs
    assert "arch-001" in combined_logs
