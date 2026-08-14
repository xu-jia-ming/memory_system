"""OPS-001 Kafka offset + shutdown consumer loop tests (U4, U12)."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from memory_system.infrastructure.kafka.archive_created_consumer import (
    MalformedArchiveCreatedEventError,
    commit_record_offset,
    run_archive_created_consumer_loop,
)


def _consumer_mock() -> MagicMock:
    consumer = MagicMock()
    consumer.getmany = AsyncMock()
    consumer.commit = AsyncMock()
    return consumer


class TestU4StopWithoutPendingRecord:
    @pytest.mark.asyncio
    async def test_should_stop_exits_without_poll_or_commit(self) -> None:
        consumer = _consumer_mock()

        processed = await run_archive_created_consumer_loop(
            consumer=consumer,
            mongodb=AsyncMock(),
            pipeline=MagicMock(),
            clock=lambda: 1_700_000_000,
            should_stop=lambda: True,
        )

        assert processed == 0
        consumer.getmany.assert_not_awaited()
        consumer.commit.assert_not_awaited()


class TestU12InFlightShutdownTimeoutPreservesOffsetSemantics:
    @pytest.mark.asyncio
    async def test_in_flight_timeout_does_not_commit(self) -> None:
        consumer = _consumer_mock()
        record = MagicMock()
        record.topic = "context.archive.created"
        record.partition = 0
        record.offset = 7
        record.key = b"user-1"
        record.value = b"{}"
        consumer.getmany = AsyncMock(
            side_effect=[
                {MagicMock(): [record]},
            ]
        )

        shutdown_started = time.monotonic()

        async def slow_process(**_kwargs: object) -> bool:
            await asyncio.sleep(3600)
            return True

        with patch(
            "memory_system.infrastructure.kafka.archive_created_consumer.process_consumer_record",
            side_effect=slow_process,
        ):
            processed = await run_archive_created_consumer_loop(
                consumer=consumer,
                mongodb=AsyncMock(),
                pipeline=MagicMock(),
                clock=lambda: 1_700_000_000,
                get_shutdown_started=lambda: shutdown_started,
                shutdown_timeout_seconds=1,
            )

        assert processed == 0
        consumer.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_malformed_record_still_raises_under_shutdown_budget(self) -> None:
        consumer = _consumer_mock()
        record = MagicMock()
        record.topic = "context.archive.created"
        record.partition = 0
        record.offset = 1
        consumer.getmany = AsyncMock(
            side_effect=[
                {MagicMock(): [record]},
            ]
        )

        shutdown_started = time.monotonic()

        with patch(
            "memory_system.infrastructure.kafka.archive_created_consumer.process_consumer_record",
            side_effect=MalformedArchiveCreatedEventError("bad payload"),
        ):
            with pytest.raises(MalformedArchiveCreatedEventError):
                await run_archive_created_consumer_loop(
                    consumer=consumer,
                    mongodb=AsyncMock(),
                    pipeline=MagicMock(),
                    clock=lambda: 1_700_000_000,
                    get_shutdown_started=lambda: shutdown_started,
                    shutdown_timeout_seconds=1,
                )

        consumer.commit.assert_not_awaited()


class TestCommitHelperRegression:
    @pytest.mark.asyncio
    async def test_commit_record_offset_commits_next_offset(self) -> None:
        consumer = _consumer_mock()
        record = MagicMock()
        record.topic = "context.archive.created"
        record.partition = 2
        record.offset = 10

        await commit_record_offset(consumer, record)

        consumer.commit.assert_awaited_once()
        committed = consumer.commit.await_args.args[0]
        tp = next(iter(committed.keys()))
        assert tp.topic == record.topic
        assert tp.partition == record.partition
        assert committed[tp] == record.offset + 1
