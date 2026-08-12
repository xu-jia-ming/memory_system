"""Elasticsearch bulk write repository for EXT-007 retrieval index sync."""

from __future__ import annotations

from typing import Any

from elasticsearch import AsyncElasticsearch

from memory_system.domain.models.retrieval_index_sync import MemoryIndexDocument


class RetrievalIndexWriteError(Exception):
    """Raised when Elasticsearch bulk upsert fails."""


class RetrievalIndexWriteRepository:
    """Bulk upsert retrieval index documents by memory_id."""

    def __init__(self, client: AsyncElasticsearch) -> None:
        self._client = client

    async def bulk_upsert(
        self,
        index_alias: str,
        documents: list[MemoryIndexDocument],
    ) -> None:
        if not documents:
            return

        operations: list[dict[str, Any]] = []
        for document in documents:
            payload = document.model_dump(mode="json")
            operations.append({"index": {"_index": index_alias, "_id": document.memory_id}})
            operations.append(payload)

        try:
            response = await self._client.bulk(
                operations=operations,
                refresh="wait_for",
            )
        except Exception as exc:
            raise RetrievalIndexWriteError("elasticsearch bulk request failed") from exc

        if response.get("errors"):
            raise RetrievalIndexWriteError("elasticsearch bulk reported item errors")

        items = response.get("items")
        if not isinstance(items, list):
            raise RetrievalIndexWriteError("elasticsearch bulk response missing items")

        for item in items:
            if not isinstance(item, dict):
                raise RetrievalIndexWriteError("elasticsearch bulk item must be an object")
            index_result = item.get("index")
            if not isinstance(index_result, dict):
                raise RetrievalIndexWriteError("elasticsearch bulk item missing index result")
            status = index_result.get("status")
            if not isinstance(status, int) or status >= 300:
                raise RetrievalIndexWriteError("elasticsearch bulk item failed")
            if index_result.get("error") is not None:
                raise RetrievalIndexWriteError("elasticsearch bulk item reported error")
