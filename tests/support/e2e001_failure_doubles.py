"""E2E-001 failure doubles: Kafka, production ES bulk wrap, close terminal fail."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, patch

from elasticsearch import AsyncElasticsearch

from memory_system.domain.enums.session_close import SessionCloseTerminalStatus
from memory_system.domain.models.retrieval_index_sync import MemoryIndexDocument
from memory_system.infrastructure.elasticsearch.retrieval_index_write_repository import (
    RetrievalIndexWriteRepository,
)


class OneShotFailingRetrievalIndexWriteRepository(RetrievalIndexWriteRepository):
    """Production ES write repo whose first real ``bulk`` call fails once."""

    remaining_failures: int = 1

    def __init__(self, client: AsyncElasticsearch) -> None:
        super().__init__(client)

    @classmethod
    def reset(cls, remaining: int = 1) -> None:
        cls.remaining_failures = remaining

    async def bulk_upsert(
        self,
        index_alias: str,
        documents: list[MemoryIndexDocument],
    ) -> None:
        if type(self).remaining_failures > 0:
            type(self).remaining_failures -= 1
            original_bulk = self._client.bulk

            async def failing_bulk(*args: Any, **kwargs: Any) -> Any:
                del args, kwargs
                raise RuntimeError("injected one-shot elasticsearch bulk failure")

            self._client.bulk = failing_bulk  # type: ignore[method-assign]
            try:
                await super().bulk_upsert(index_alias, documents)
            finally:
                self._client.bulk = original_bulk  # type: ignore[method-assign]
            return
        await super().bulk_upsert(index_alias, documents)


def install_one_shot_production_es_bulk_failure(monkeypatch: Any) -> None:
    """Patch production RetrievalIndexWriteRepository; first bulk fails, later succeed."""
    OneShotFailingRetrievalIndexWriteRepository.reset(remaining=1)
    monkeypatch.setattr(
        "memory_system.infrastructure.elasticsearch.retrieval_index_write_repository"
        ".RetrievalIndexWriteRepository",
        OneShotFailingRetrievalIndexWriteRepository,
    )


@contextmanager
def kafka_send_and_wait_fail(producer: Any) -> Iterator[None]:
    """Fail Kafka ``send_and_wait`` after Mongo Archive is already the save point."""
    original = producer.send_and_wait
    producer.send_and_wait = AsyncMock(
        side_effect=RuntimeError("injected kafka publish failure"),
    )
    try:
        yield
    finally:
        producer.send_and_wait = original


@contextmanager
def close_terminal_delete_fail() -> Iterator[None]:
    """Inject Redis terminal-delete failure so close returns close_incomplete."""
    with patch(
        "memory_system.domain.services.session_close_service.execute_terminal_delete_lua",
        new_callable=AsyncMock,
        return_value=SessionCloseTerminalStatus.INVALID_SESSION_STATE,
    ):
        yield
