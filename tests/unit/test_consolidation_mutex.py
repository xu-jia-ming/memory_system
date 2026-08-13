"""Unit tests for consolidation mutex (CON-004 U5, U6, F1)."""

from __future__ import annotations

import asyncio

import pytest

from memory_system.infrastructure.consolidation_mutex import ConsolidationMutex


class TestU5OverlapSkip:
    @pytest.mark.asyncio
    async def test_second_acquire_fails_and_increments_skipped(self) -> None:
        mutex = ConsolidationMutex()
        assert await mutex.try_acquire() is True
        assert await mutex.try_acquire() is False
        assert mutex.skipped_trigger_count == 1
        await mutex.release()


class TestU6ExceptionRelease:
    @pytest.mark.asyncio
    async def test_release_after_exception_allows_reacquire(self) -> None:
        mutex = ConsolidationMutex()
        assert await mutex.try_acquire() is True
        try:
            raise RuntimeError("run failed")
        except RuntimeError:
            await mutex.release()
        assert await mutex.try_acquire() is True
        await mutex.release()
        assert await mutex.try_acquire() is True
        await mutex.release()


class TestF1ConcurrentTriggers:
    @pytest.mark.asyncio
    async def test_only_one_concurrent_acquire_succeeds(self) -> None:
        mutex = ConsolidationMutex()
        results: list[bool] = []

        async def attempt() -> None:
            results.append(await mutex.try_acquire())

        await asyncio.gather(attempt(), attempt())
        assert results.count(True) == 1
        assert results.count(False) == 1
        assert mutex.skipped_trigger_count == 1
        await mutex.release()
