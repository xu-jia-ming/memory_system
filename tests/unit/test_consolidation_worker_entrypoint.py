"""Unit tests for consolidation worker entrypoint (CON-004 W1, W2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from memory_system.entrypoints import consolidation_worker
from memory_system.settings import get_settings

SETTINGS = get_settings()


class TestW1SettingsFailure:
    def test_main_returns_exit_code_one_on_settings_failure(self) -> None:
        with patch(
            "memory_system.entrypoints.consolidation_worker.get_settings",
            side_effect=ValueError("invalid"),
        ):
            assert consolidation_worker.main() == 1


class TestW2EnabledSchedulerWiring:
    @pytest.mark.asyncio
    async def test_run_worker_registers_scheduler_when_enabled(self) -> None:
        mock_scheduler = MagicMock()
        mock_scheduler.start = MagicMock()
        mock_scheduler.shutdown = MagicMock()

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_session.run = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_driver.session.return_value = mock_session
        mock_driver.close = AsyncMock()

        with (
            patch(
                "memory_system.entrypoints.consolidation_worker.AsyncGraphDatabase.driver",
                return_value=mock_driver,
            ),
            patch(
                "memory_system.entrypoints.consolidation_worker.create_consolidation_scheduler",
                return_value=mock_scheduler,
            ) as create_scheduler,
            patch(
                "memory_system.entrypoints.consolidation_worker._install_stop_handlers",
                side_effect=lambda event: event.set(),
            ),
        ):
            await consolidation_worker._run_worker(SETTINGS)

        create_scheduler.assert_called_once()
        mock_scheduler.start.assert_called_once()
        mock_scheduler.shutdown.assert_called_once_with(wait=True)
