"""APScheduler registration for consolidation runs (§3.22)."""

from __future__ import annotations

import contextvars
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from apscheduler.events import (  # type: ignore[import-untyped]
    EVENT_JOB_SUBMITTED,
    JobSubmissionEvent,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]

from memory_system.settings import Settings

CONSOLIDATION_JOB_ID = "memory_consolidation_run"

_scheduled_run_time_var: contextvars.ContextVar[datetime | None] = contextvars.ContextVar(
    "consolidation_scheduled_run_time",
    default=None,
)

RunCallback = Callable[[int], Awaitable[None]]


def evaluation_time_from_scheduled_run(scheduled_run_time: datetime) -> int:
    """Convert APScheduler scheduled fire time to UTC Unix seconds."""
    if scheduled_run_time.tzinfo is None:
        scheduled_run_time = scheduled_run_time.replace(tzinfo=UTC)
    utc_time = scheduled_run_time.astimezone(UTC)
    return int(utc_time.timestamp())


def _on_job_submitted(event: JobSubmissionEvent) -> None:
    if event.job_id != CONSOLIDATION_JOB_ID:
        return
    if event.scheduled_run_times:
        _scheduled_run_time_var.set(event.scheduled_run_times[0])


def create_consolidation_scheduler(
    settings: Settings,
    run_callback: RunCallback,
) -> AsyncIOScheduler | None:
    consolidation = settings.memory_consolidation
    if not consolidation.enabled:
        return None

    scheduler = AsyncIOScheduler(timezone=consolidation.timezone)
    scheduler.add_listener(_on_job_submitted, EVENT_JOB_SUBMITTED)

    async def memory_consolidation_run() -> None:
        scheduled_run_time = _scheduled_run_time_var.get()
        if scheduled_run_time is None:
            raise RuntimeError("missing scheduled_run_time for consolidation job")
        evaluation_time = evaluation_time_from_scheduled_run(scheduled_run_time)
        await run_callback(evaluation_time)

    scheduler.add_job(
        memory_consolidation_run,
        CronTrigger.from_crontab(
            consolidation.schedule_cron,
            timezone=consolidation.timezone,
        ),
        id=CONSOLIDATION_JOB_ID,
        max_instances=consolidation.scheduler_max_instances,
        coalesce=consolidation.scheduler_coalesce,
        misfire_grace_time=consolidation.scheduler_misfire_grace_time_seconds,
        replace_existing=True,
    )
    return scheduler
