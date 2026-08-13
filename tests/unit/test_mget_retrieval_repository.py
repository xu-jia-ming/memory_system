"""Unit tests for MGET retrieval repository (RET-003 C1/C4)."""

from __future__ import annotations

from typing import Any

import pytest
from elasticsearch import ConnectionError as EsConnectionError

from memory_system.infrastructure.elasticsearch.mget_retrieval_repository import (
    MgetRetrievalError,
    MgetRetrievalRepository,
)
from memory_system.settings import get_settings


class FakeMgetClient:
    def __init__(self, *, response: Any = None, fail: bool = False) -> None:
        self.response = response
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    def options(self, **kwargs: Any) -> FakeMgetClient:
        self.options_kwargs = kwargs
        return self

    async def mget(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self.fail:
            raise EsConnectionError("transport failed")
        return self.response or {
            "docs": [
                {"_id": "mem-1", "found": True},
                {"_id": "mem-2", "found": False},
            ],
        }


@pytest.mark.asyncio
async def test_c1_mget_request_body_and_index_from_settings() -> None:
    client = FakeMgetClient()
    repo = MgetRetrievalRepository(client)
    settings = get_settings().memory_retrieval
    body = repo.build_mget_body(["mem-2", "mem-1"])
    assert body == {"ids": ["mem-1", "mem-2"]}

    found = await repo.exists_many(
        index_name=settings.index_name,
        memory_ids=["mem-2", "mem-1"],
        request_timeout=float(settings.elasticsearch_timeout_seconds),
    )
    assert found == {"mem-1"}
    assert client.calls[0]["index"] == settings.index_name
    assert client.calls[0]["body"] == {"ids": ["mem-1", "mem-2"]}
    assert client.calls[0]["source"] is False


@pytest.mark.asyncio
async def test_c4_mget_does_not_read_source() -> None:
    client = FakeMgetClient()
    repo = MgetRetrievalRepository(client)
    await repo.exists_many(
        index_name="memory_retrieval_current",
        memory_ids=["mem-1"],
        request_timeout=5.0,
    )
    assert client.calls[0]["source"] is False


@pytest.mark.asyncio
async def test_mget_transport_failure_raises() -> None:
    client = FakeMgetClient(fail=True)
    repo = MgetRetrievalRepository(client)
    with pytest.raises(MgetRetrievalError):
        await repo.exists_many(
            index_name="memory_retrieval_current",
            memory_ids=["mem-1"],
            request_timeout=5.0,
        )
