"""Process-local asyncio mutex for consolidation runs (§2.3.4)."""

from __future__ import annotations

import asyncio


class ConsolidationMutex:
    """Non-blocking process-local mutex for a single consolidation run."""

    def __init__(self) -> None:
        self._guard = asyncio.Lock()
        self._held = False
        self.skipped_trigger_count = 0

    async def try_acquire(self) -> bool:
        async with self._guard:
            if self._held:
                self.skipped_trigger_count += 1
                return False
            self._held = True
            return True

    async def release(self) -> None:
        async with self._guard:
            self._held = False

    def is_held(self) -> bool:
        return self._held
