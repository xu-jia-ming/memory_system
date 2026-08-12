"""Read-only context_archive message timestamp lookup (EXT-006 LD-9)."""

from __future__ import annotations

from typing import Any

from pymongo import AsyncMongoClient

from memory_system.domain.models.graph_write import GraphWriteAbort
from memory_system.infrastructure.mongodb.context_archive_repository import (
    find_context_archive_by_id,
)


class GraphWriteAbortError(Exception):
    """Abort graph write without terminal persistence."""

    def __init__(self, abort: GraphWriteAbort) -> None:
        super().__init__(abort.kind)
        self.abort = abort


class ContextArchiveMessageTimestampRepository:
    """Resolve message timestamps from persisted context_archive (read-only)."""

    async def resolve_timestamps(
        self,
        mongodb: AsyncMongoClient[Any],
        archive_id: str,
        message_ids: list[str],
    ) -> dict[str, int]:
        archive = await find_context_archive_by_id(mongodb, archive_id)
        if archive is None:
            raise GraphWriteAbortError(GraphWriteAbort())

        timestamp_by_id = {message.message_id: message.timestamp for message in archive.messages}
        resolved: dict[str, int] = {}
        for message_id in message_ids:
            timestamp = timestamp_by_id.get(message_id)
            if timestamp is None:
                raise GraphWriteAbortError(GraphWriteAbort())
            resolved[message_id] = timestamp
        return resolved

    async def resolve_source_time_range(
        self,
        mongodb: AsyncMongoClient[Any],
        archive_id: str,
        source_message_ids: list[str],
        candidate_source_time: int,
    ) -> tuple[int, int]:
        if not source_message_ids:
            raise GraphWriteAbortError(GraphWriteAbort())
        if len(source_message_ids) == 1:
            return candidate_source_time, candidate_source_time

        timestamps = await self.resolve_timestamps(mongodb, archive_id, source_message_ids)
        values = [timestamps[message_id] for message_id in source_message_ids]
        return min(values), max(values)
