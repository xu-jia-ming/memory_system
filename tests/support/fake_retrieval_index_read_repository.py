"""Fake retrieval index read repository for EXT-007 tests."""

from __future__ import annotations

from memory_system.domain.models.retrieval_index_sync import MemoryIndexRow


class FakeRetrievalIndexReadRepository:
    def __init__(
        self,
        *,
        related_memory_ids: set[str] | None = None,
        entity_linked_memory_ids: set[str] | None = None,
        rows: list[MemoryIndexRow] | None = None,
        fail_on_load: bool = False,
    ) -> None:
        self.related_memory_ids = related_memory_ids or set()
        self.entity_linked_memory_ids = entity_linked_memory_ids or set()
        self.rows = rows or []
        self.fail_on_load = fail_on_load
        self.expand_related_calls: list[tuple[str, set[str]]] = []
        self.expand_entity_calls: list[tuple[str, list[str]]] = []
        self.load_calls: list[tuple[str, set[str]]] = []

    async def expand_related_memory_ids(
        self,
        user_id: str,
        seed_memory_ids: set[str],
    ) -> set[str]:
        self.expand_related_calls.append((user_id, set(seed_memory_ids)))
        return set(self.related_memory_ids)

    async def expand_entity_linked_memory_ids(
        self,
        user_id: str,
        entity_ids: list[str],
    ) -> set[str]:
        self.expand_entity_calls.append((user_id, list(entity_ids)))
        return set(self.entity_linked_memory_ids)

    async def load_memory_index_rows(
        self,
        user_id: str,
        memory_ids: set[str],
    ) -> list[MemoryIndexRow]:
        if self.fail_on_load:
            raise RuntimeError("neo4j read failed")
        self.load_calls.append((user_id, set(memory_ids)))
        return [row for row in self.rows if row.memory_id in memory_ids]
