"""Fake retrieval index write repository for EXT-007 tests."""

from __future__ import annotations

from memory_system.domain.models.retrieval_index_sync import MemoryIndexDocument
from memory_system.infrastructure.elasticsearch.retrieval_index_write_repository import (
    RetrievalIndexWriteError,
)


class FakeRetrievalIndexWriteRepository:
    def __init__(self, *, fail: bool = False, fail_on_memory_id: str | None = None) -> None:
        self.fail = fail
        self.fail_on_memory_id = fail_on_memory_id
        self.calls: list[tuple[str, list[MemoryIndexDocument]]] = []

    async def bulk_upsert(
        self,
        index_alias: str,
        documents: list[MemoryIndexDocument],
    ) -> None:
        if self.fail:
            raise RetrievalIndexWriteError("bulk failed")
        if self.fail_on_memory_id is not None:
            for document in documents:
                if document.memory_id == self.fail_on_memory_id:
                    raise RetrievalIndexWriteError("bulk item failed")
        self.calls.append((index_alias, list(documents)))
