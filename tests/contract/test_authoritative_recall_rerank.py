"""Contract tests for authoritative recall rerank integration."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from tests.support.fake_rerank_client import FakeRerankClient

from memory_system.domain.models.authoritative_recall import AuthoritativeRecallQuery
from memory_system.domain.models.hybrid_retrieval import (
    FusedRetrievalCandidate,
    HybridRetrievalSuccess,
)
from memory_system.domain.models.retrieval_memory_snapshot import (
    RetrievalEntitySnapshot,
    RetrievalMemorySnapshot,
)
from memory_system.domain.services.authoritative_recall_service import AuthoritativeRecallService
from memory_system.domain.services.graph_expansion_ranker import ExpansionEdge
from memory_system.infrastructure.rerank.types import RerankScoredDocument
from memory_system.settings import get_settings

USER_ID = "user-a"


def _snapshot(memory_id: str) -> RetrievalMemorySnapshot:
    return RetrievalMemorySnapshot(
        memory_id=memory_id,
        user_id=USER_ID,
        memory_type="fact",
        status="active",
        content=f"content-{memory_id}",
        subject_entity_id="ent-subject",
        predicate="works_on",
        object_entity_id="ent-object",
        object_value=None,
        event_status=None,
        start_time=None,
        end_time=None,
        original_time_text=None,
        importance=0.8,
        confidence=0.9,
        retrieval_count=1,
        last_retrieved_time=None,
        latest_source_time=150,
        updated_time=1_700_000_000,
        subject_entity=RetrievalEntitySnapshot(
            entity_id="ent-subject",
            canonical_name="Subject",
            aliases=[],
            entity_type="concept",
            normalized_name="subject",
        ),
        object_entity=RetrievalEntitySnapshot(
            entity_id="ent-object",
            canonical_name="Object",
            aliases=[],
            entity_type="concept",
            normalized_name="object",
        ),
    )


def _fused(memory_id: str, *, rank: int) -> FusedRetrievalCandidate:
    return FusedRetrievalCandidate(
        memory_id=memory_id,
        bm25_rank=rank,
        vector_rank=None,
        bm25_score=1.0 / rank,
        vector_score=None,
        retrieval_source=["bm25"],
        rrf_score=1.0 / rank,
        min_available_rank=rank,
        normalized_retrieval_score=1.0 / rank,
    )


class FakeNeo4jRepo:
    def __init__(
        self,
        *,
        snapshots: dict[str, RetrievalMemorySnapshot],
        expansion_edges: list[ExpansionEdge],
    ) -> None:
        self.snapshots = snapshots
        self.expansion_edges = expansion_edges
        self.expand_calls: list[list[str]] = []

    async def load_memories(
        self,
        user_id: str,
        memory_ids: list[str],
    ) -> dict[str, RetrievalMemorySnapshot]:
        del user_id
        return {
            memory_id: self.snapshots[memory_id]
            for memory_id in memory_ids
            if memory_id in self.snapshots
        }

    async def expand_one_hop(
        self,
        user_id: str,
        seed_ids: list[str],
    ) -> list[ExpansionEdge]:
        del user_id
        self.expand_calls.append(list(seed_ids))
        return list(self.expansion_edges)


class FakeMgetRepo:
    async def exists_many(
        self,
        *,
        index_name: str,
        memory_ids: list[str],
        request_timeout: float,
    ) -> set[str]:
        del index_name, request_timeout
        return set(memory_ids)


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _settings_rerank_enabled() -> Any:
    settings = get_settings()
    return settings.model_copy(
        update={
            "memory_retrieval": settings.memory_retrieval.model_copy(
                update={"rerank_enabled": True},
            ),
        },
    )


@pytest.mark.asyncio
async def test_authoritative_recall_uses_rerank_order_for_graph_expand_seeds() -> None:
    rerank_client = FakeRerankClient(
        results=[
            RerankScoredDocument(index=2, relevance_score=0.99),
            RerankScoredDocument(index=1, relevance_score=0.88),
            RerankScoredDocument(index=0, relevance_score=0.77),
        ],
    )
    neo4j = FakeNeo4jRepo(
        snapshots={
            "mem-a": _snapshot("mem-a"),
            "mem-b": _snapshot("mem-b"),
            "mem-c": _snapshot("mem-c"),
            "mem-expanded": _snapshot("mem-expanded"),
        },
        expansion_edges=[
            ExpansionEdge("mem-c", "mem-expanded", 0, 1.0, 100, "fact", "active"),
        ],
    )
    service = AuthoritativeRecallService(
        neo4j_repo=neo4j,
        mget_repo=FakeMgetRepo(),
        settings=_settings_rerank_enabled(),
        rerank_client=rerank_client,
    )
    outcome = await service.recall(
        AuthoritativeRecallQuery(
            hybrid_success=HybridRetrievalSuccess(
                user_id=USER_ID,
                retrieval_mode="hybrid",
                candidates=[
                    _fused("mem-a", rank=1),
                    _fused("mem-b", rank=2),
                    _fused("mem-c", rank=3),
                ],
                effective_channel_count=2,
            ),
            graph_expand=True,
            normalized_query="graph seed query",
        ),
    )
    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert [item.memory_id for item in outcome.success.direct_candidates] == [
        "mem-c",
        "mem-b",
        "mem-a",
    ]
    assert neo4j.expand_calls == [["mem-c", "mem-b", "mem-a"]]
    assert rerank_client.calls[0]["query"] == "graph seed query"


@pytest.mark.asyncio
async def test_authoritative_recall_propagates_rerank_failed_warning() -> None:
    from memory_system.infrastructure.rerank.errors import RerankServiceError

    rerank_client = FakeRerankClient(
        error=RerankServiceError(
            code="rerank_failed",
            provider="siliconflow",
            status_code=500,
            trace_id=None,
            sanitized_message="server error",
        ),
    )
    neo4j = FakeNeo4jRepo(
        snapshots={"mem-a": _snapshot("mem-a")},
        expansion_edges=[],
    )
    service = AuthoritativeRecallService(
        neo4j_repo=neo4j,
        mget_repo=FakeMgetRepo(),
        settings=_settings_rerank_enabled(),
        rerank_client=rerank_client,
    )
    outcome = await service.recall(
        AuthoritativeRecallQuery(
            hybrid_success=HybridRetrievalSuccess(
                user_id=USER_ID,
                retrieval_mode="hybrid",
                candidates=[_fused("mem-a", rank=1)],
                effective_channel_count=2,
            ),
            graph_expand=False,
            normalized_query="query",
        ),
    )
    assert outcome.success is not None
    assert any(w.kind == "rerank_failed" for w in outcome.success.warnings)
    assert outcome.success.direct_candidates[0].normalized_retrieval_score == 1.0
