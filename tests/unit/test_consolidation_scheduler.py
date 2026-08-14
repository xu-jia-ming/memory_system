"""Unit tests for consolidation scheduler (CON-004 U14..U17)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from apscheduler.schedulers.base import STATE_STOPPED  # type: ignore[import-untyped]
from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]

from memory_system.infrastructure.scheduling.consolidation_scheduler import (
    CONSOLIDATION_JOB_ID,
    create_consolidation_scheduler,
    evaluation_time_from_scheduled_run,
)
from memory_system.settings import get_settings

SETTINGS = get_settings()


class TestU14JobRegistration:
    def test_cron_trigger_matches_settings(self) -> None:
        consolidation = SETTINGS.memory_consolidation
        trigger = CronTrigger.from_crontab(
            consolidation.schedule_cron,
            timezone=consolidation.timezone,
        )
        assert str(trigger.timezone) == "UTC"

    def test_scheduler_registers_job_parameters(self) -> None:
        callback = AsyncMock()
        scheduler = create_consolidation_scheduler(SETTINGS, callback)
        assert scheduler is not None
        job = scheduler.get_job(CONSOLIDATION_JOB_ID)
        assert job is not None
        consolidation = SETTINGS.memory_consolidation
        assert job.max_instances == consolidation.scheduler_max_instances
        assert job.coalesce == consolidation.scheduler_coalesce
        assert job.misfire_grace_time == consolidation.scheduler_misfire_grace_time_seconds

    def test_evaluation_time_from_scheduled_run_utc(self) -> None:
        scheduled = datetime(2026, 8, 13, 3, 0, 0, tzinfo=UTC)
        assert evaluation_time_from_scheduled_run(scheduled) == int(scheduled.timestamp())


class TestU15Disabled:
    def test_enabled_false_returns_none(self) -> None:
        settings = SETTINGS.model_copy(
            update={
                "memory_consolidation": SETTINGS.memory_consolidation.model_copy(
                    update={"enabled": False},
                ),
            },
        )
        scheduler = create_consolidation_scheduler(settings, AsyncMock())
        assert scheduler is None


class TestU16InvalidConfig:
    def test_invalid_cron_rejected_by_cron_trigger(self) -> None:
        with pytest.raises(ValueError):
            CronTrigger.from_crontab("not a cron", timezone="UTC")

    def test_worker_main_exits_nonzero_on_settings_failure(self) -> None:
        from unittest.mock import patch

        from memory_system.entrypoints.consolidation_worker import main

        with patch(
            "memory_system.entrypoints.consolidation_worker.get_settings",
            side_effect=ValueError("consolidation_invalid_config"),
        ):
            assert main() == 1


class TestU17Shutdown:
    @pytest.mark.asyncio
    async def test_shutdown_stops_scheduler(self) -> None:
        callback = AsyncMock()
        scheduler = create_consolidation_scheduler(SETTINGS, callback)
        assert scheduler is not None
        scheduler.start()
        scheduler.shutdown(wait=True)
        await asyncio.sleep(0)
        assert scheduler.state == STATE_STOPPED
