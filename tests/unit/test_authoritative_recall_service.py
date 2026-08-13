"""Unit tests for authoritative recall service orchestration (RET-003)."""

from __future__ import annotations

from typing import Any

import pytest

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
from memory_system.infrastructure.elasticsearch.mget_retrieval_repository import MgetRetrievalError
from memory_system.infrastructure.neo4j.retrieval_memory_read_repository import (
    RetrievalMemoryReadError,
)
from memory_system.settings import get_settings

USER_ID = "user-a"


def make_memory_snapshot(
    *,
    memory_id: str = "mem-1",
    user_id: str = USER_ID,
    memory_type: str = "fact",
    status: str = "active",
    importance: float = 0.8,
    latest_source_time: int | None = 150,
) -> RetrievalMemorySnapshot:
    return RetrievalMemorySnapshot(
        memory_id=memory_id,
        user_id=user_id,
        memory_type=memory_type,
        status=status,
        content=f"content-{memory_id}",
        subject_entity_id="ent-subject",
        predicate="works_on",
        object_entity_id="ent-object",
        object_value=None,
        event_status=None,
        start_time=None,
        end_time=None,
        original_time_text=None,
        importance=importance,
        confidence=0.9,
        retrieval_count=1,
        last_retrieved_time=None,
        latest_source_time=latest_source_time,
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


def make_fused(
    *,
    memory_id: str = "mem-1",
    min_available_rank: int = 1,
    normalized_retrieval_score: float | None = 0.8,
    retrieval_source: list[str] | None = None,
) -> FusedRetrievalCandidate:
    sources: list[Any] = retrieval_source or ["bm25"]
    return FusedRetrievalCandidate(
        memory_id=memory_id,
        bm25_rank=1,
        vector_rank=None,
        bm25_score=1.5,
        vector_score=None,
        retrieval_source=sources,
        rrf_score=0.5,
        min_available_rank=min_available_rank,
        normalized_retrieval_score=normalized_retrieval_score,
    )


def make_validated_direct(
    *,
    memory_id: str = "mem-1",
    normalized_retrieval_score: float | None = 0.8,
    retrieval_source: list[str] | None = None,
) -> Any:
    from memory_system.domain.models.authoritative_recall import ValidatedRetrievalCandidate

    fused = make_fused(
        memory_id=memory_id,
        normalized_retrieval_score=normalized_retrieval_score,
        retrieval_source=retrieval_source or ["bm25"],
    )
    return ValidatedRetrievalCandidate(
        memory_id=memory_id,
        bm25_rank=fused.bm25_rank,
        vector_rank=fused.vector_rank,
        bm25_score=fused.bm25_score,
        vector_score=fused.vector_score,
        retrieval_source=list(fused.retrieval_source),
        rrf_score=fused.rrf_score,
        min_available_rank=fused.min_available_rank,
        normalized_retrieval_score=fused.normalized_retrieval_score,
        graph_retrieval_score=None,
        candidate_origin="direct",
        memory=make_memory_snapshot(memory_id=memory_id),
    )


def make_hybrid_success(
    *,
    candidates: list[FusedRetrievalCandidate] | None = None,
    user_id: str = USER_ID,
) -> HybridRetrievalSuccess:
    if candidates is None:
        resolved_candidates = [make_fused()]
    else:
        resolved_candidates = candidates
    return HybridRetrievalSuccess(
        user_id=user_id,
        retrieval_mode="hybrid",
        candidates=resolved_candidates,
        effective_channel_count=2,
    )


class FakeNeo4jRepo:
    def __init__(
        self,
        *,
        snapshots: dict[str, RetrievalMemorySnapshot] | None = None,
        expansion_edges: list[ExpansionEdge] | None = None,
        fail_load: bool = False,
        fail_expand: bool = False,
    ) -> None:
        self.snapshots = snapshots or {}
        self.expansion_edges = expansion_edges or []
        self.fail_load = fail_load
        self.fail_expand = fail_expand
        self.load_calls: list[tuple[str, list[str]]] = []
        self.expand_calls: list[tuple[str, list[str]]] = []

    async def load_memories(
        self,
        user_id: str,
        memory_ids: list[str],
    ) -> dict[str, RetrievalMemorySnapshot]:
        self.load_calls.append((user_id, memory_ids))
        if self.fail_load:
            raise RetrievalMemoryReadError("neo4j load failed", retryable=True)
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
        self.expand_calls.append((user_id, seed_ids))
        if self.fail_expand:
            raise RetrievalMemoryReadError("neo4j expand failed", retryable=True)
        return list(self.expansion_edges)


class FakeMgetRepo:
    def __init__(
        self,
        *,
        found_ids: set[str] | None = None,
        fail: bool = False,
    ) -> None:
        self.found_ids = found_ids if found_ids is not None else set()
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    async def exists_many(
        self,
        *,
        index_name: str,
        memory_ids: list[str],
        request_timeout: float,
    ) -> set[str]:
        self.calls.append(
            {
                "index_name": index_name,
                "memory_ids": memory_ids,
                "request_timeout": request_timeout,
            },
        )
        if self.fail:
            raise MgetRetrievalError("mget failed", retryable=True)
        return {memory_id for memory_id in memory_ids if memory_id in self.found_ids}


def _service(
    neo4j: FakeNeo4jRepo | None = None,
    mget: FakeMgetRepo | None = None,
) -> AuthoritativeRecallService:
    return AuthoritativeRecallService(
        neo4j_repo=neo4j or FakeNeo4jRepo(),
        mget_repo=mget or FakeMgetRepo(),
        settings=get_settings(),
    )


@pytest.mark.asyncio
async def test_u4_neo4j_missing_seed_dirty_index() -> None:
    service = _service(FakeNeo4jRepo(snapshots={}))
    outcome = await service.recall(
        AuthoritativeRecallQuery(hybrid_success=make_hybrid_success()),
    )
    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert outcome.success.direct_candidates == []
    assert outcome.success.warnings[0].kind == "dirty_index_document"
    assert outcome.success.warnings[0].memory_id == "mem-1"


@pytest.mark.asyncio
async def test_u5_stale_index_document() -> None:
    snapshot = make_memory_snapshot(status="superseded")
    service = _service(FakeNeo4jRepo(snapshots={"mem-1": snapshot}))
    outcome = await service.recall(
        AuthoritativeRecallQuery(
            hybrid_success=make_hybrid_success(),
            include_history=False,
        ),
    )
    assert outcome.success is not None
    assert outcome.success.direct_candidates == []
    assert any(w.kind == "stale_index_document" for w in outcome.success.warnings)


@pytest.mark.asyncio
async def test_u6_wrong_user_discarded() -> None:
    snapshot = make_memory_snapshot(user_id="other-user")
    service = _service(FakeNeo4jRepo(snapshots={"mem-1": snapshot}))
    outcome = await service.recall(
        AuthoritativeRecallQuery(hybrid_success=make_hybrid_success()),
    )
    assert outcome.success is not None
    assert outcome.success.direct_candidates == []
    assert outcome.success.warnings == []


@pytest.mark.asyncio
async def test_u7_graph_expand_false_skips_expand() -> None:
    neo4j = FakeNeo4jRepo(snapshots={"mem-1": make_memory_snapshot()})
    service = _service(neo4j)
    outcome = await service.recall(
        AuthoritativeRecallQuery(
            hybrid_success=make_hybrid_success(),
            graph_expand=False,
        ),
    )
    assert outcome.success is not None
    assert len(outcome.success.direct_candidates) == 1
    assert neo4j.expand_calls == []


@pytest.mark.asyncio
async def test_u14_mget_not_found_discards_expanded() -> None:
    neo4j = FakeNeo4jRepo(
        snapshots={
            "mem-seed": make_memory_snapshot(memory_id="mem-seed"),
            "mem-expanded": make_memory_snapshot(memory_id="mem-expanded"),
        },
        expansion_edges=[
            ExpansionEdge("mem-seed", "mem-expanded", 0, 1.0, 100, "fact", "active"),
        ],
    )
    mget = FakeMgetRepo(found_ids=set())
    service = _service(neo4j, mget)
    outcome = await service.recall(
        AuthoritativeRecallQuery(
            hybrid_success=make_hybrid_success(candidates=[make_fused(memory_id="mem-seed")]),
        ),
    )
    assert outcome.success is not None
    assert outcome.success.expanded_candidates == []


@pytest.mark.asyncio
async def test_u15_expansion_edges_filtered_by_status() -> None:
    neo4j = FakeNeo4jRepo(
        snapshots={"mem-seed": make_memory_snapshot(memory_id="mem-seed")},
        expansion_edges=[
            ExpansionEdge("mem-seed", "mem-bad", 0, 1.0, 100, "fact", "superseded"),
        ],
    )
    service = _service(neo4j, FakeMgetRepo(found_ids={"mem-bad"}))
    outcome = await service.recall(
        AuthoritativeRecallQuery(
            hybrid_success=make_hybrid_success(candidates=[make_fused(memory_id="mem-seed")]),
            include_history=False,
        ),
    )
    assert outcome.success is not None
    assert outcome.success.expanded_candidates == []


@pytest.mark.asyncio
async def test_u17_neo4j_expand_failure_degrades() -> None:
    neo4j = FakeNeo4jRepo(
        snapshots={"mem-1": make_memory_snapshot()},
        fail_expand=True,
    )
    service = _service(neo4j)
    outcome = await service.recall(
        AuthoritativeRecallQuery(hybrid_success=make_hybrid_success()),
    )
    assert outcome.success is not None
    assert len(outcome.success.direct_candidates) == 1
    assert any(w.kind == "graph_expansion_failed" for w in outcome.success.warnings)


@pytest.mark.asyncio
async def test_u18_mget_failure_degrades() -> None:
    neo4j = FakeNeo4jRepo(
        snapshots={
            "mem-seed": make_memory_snapshot(memory_id="mem-seed"),
            "mem-expanded": make_memory_snapshot(memory_id="mem-expanded"),
        },
        expansion_edges=[
            ExpansionEdge("mem-seed", "mem-expanded", 0, 1.0, 100, "fact", "active"),
        ],
    )
    service = _service(neo4j, FakeMgetRepo(fail=True))
    outcome = await service.recall(
        AuthoritativeRecallQuery(
            hybrid_success=make_hybrid_success(candidates=[make_fused(memory_id="mem-seed")]),
        ),
    )
    assert outcome.success is not None
    assert len(outcome.success.direct_candidates) == 1
    assert outcome.success.expanded_candidates == []
    assert any(w.kind == "graph_expansion_failed" for w in outcome.success.warnings)


@pytest.mark.asyncio
async def test_u19_neo4j_batch_read_failure() -> None:
    service = _service(FakeNeo4jRepo(fail_load=True))
    outcome = await service.recall(
        AuthoritativeRecallQuery(hybrid_success=make_hybrid_success()),
    )
    assert outcome.outcome == "failure"
    assert outcome.failure is not None
    assert outcome.failure.kind == "neo4j_read_failure"


@pytest.mark.asyncio
async def test_u20_empty_rrf_candidates() -> None:
    neo4j = FakeNeo4jRepo()
    service = _service(neo4j)
    outcome = await service.recall(
        AuthoritativeRecallQuery(hybrid_success=make_hybrid_success(candidates=[])),
    )
    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert outcome.success.direct_candidates == []
    assert neo4j.load_calls == []


@pytest.mark.asyncio
async def test_u22_pure_expanded_scalar_fields_none() -> None:
    neo4j = FakeNeo4jRepo(
        snapshots={
            "mem-seed": make_memory_snapshot(memory_id="mem-seed"),
            "mem-expanded": make_memory_snapshot(memory_id="mem-expanded"),
        },
        expansion_edges=[
            ExpansionEdge("mem-seed", "mem-expanded", 0, 1.0, 100, "fact", "active"),
        ],
    )
    mget = FakeMgetRepo(found_ids={"mem-expanded"})
    service = _service(neo4j, mget)
    outcome = await service.recall(
        AuthoritativeRecallQuery(
            hybrid_success=make_hybrid_success(candidates=[make_fused(memory_id="mem-seed")]),
        ),
    )
    assert outcome.success is not None
    assert len(outcome.success.expanded_candidates) == 1
    expanded = outcome.success.expanded_candidates[0]
    assert expanded.bm25_rank is None
    assert expanded.vector_rank is None
    assert expanded.bm25_score is None
    assert expanded.vector_score is None
    assert expanded.rrf_score is None
    assert expanded.min_available_rank is None
    assert expanded.normalized_retrieval_score is None
    assert expanded.graph_retrieval_score is not None
    assert expanded.candidate_origin == "expanded"
