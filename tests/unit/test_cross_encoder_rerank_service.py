"""Unit tests for cross-encoder rerank domain service."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from tests.support.fake_rerank_client import FakeRerankClient

from memory_system.domain.models.authoritative_recall import ValidatedRetrievalCandidate
from memory_system.domain.models.hybrid_retrieval import FusedRetrievalCandidate
from memory_system.domain.models.retrieval_memory_snapshot import (
    RetrievalEntitySnapshot,
    RetrievalMemorySnapshot,
)
from memory_system.domain.services.cross_encoder_rerank_service import rerank_direct_candidates
from memory_system.infrastructure.rerank.errors import RerankServiceError
from memory_system.infrastructure.rerank.types import RerankScoredDocument
from memory_system.settings import get_settings

USER_ID = "user-a"


def _snapshot(memory_id: str, *, content: str | None = None) -> RetrievalMemorySnapshot:
    resolved_content = f"content-{memory_id}" if content is None else content
    return RetrievalMemorySnapshot(
        memory_id=memory_id,
        user_id=USER_ID,
        memory_type="fact",
        status="active",
        content=resolved_content,
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


def _direct(
    memory_id: str,
    *,
    normalized_retrieval_score: float,
    content: str | None = None,
) -> ValidatedRetrievalCandidate:
    fused = FusedRetrievalCandidate(
        memory_id=memory_id,
        bm25_rank=1,
        vector_rank=None,
        bm25_score=1.5,
        vector_score=None,
        retrieval_source=["bm25"],
        rrf_score=0.5,
        min_available_rank=1,
        normalized_retrieval_score=normalized_retrieval_score,
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
        memory=_snapshot(
            memory_id,
            content=content,
        ),
    )


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _settings_with_rerank_enabled(enabled: bool):
    settings = get_settings()
    return settings.model_copy(
        update={
            "memory_retrieval": settings.memory_retrieval.model_copy(
                update={"rerank_enabled": enabled},
            ),
        },
    )


@pytest.mark.asyncio
async def test_rerank_reorders_candidates_and_updates_scores() -> None:
    candidates = [
        _direct("mem-a", normalized_retrieval_score=0.3),
        _direct("mem-b", normalized_retrieval_score=0.2),
        _direct("mem-c", normalized_retrieval_score=0.1),
    ]
    fake_client = FakeRerankClient(
        results=[
            RerankScoredDocument(index=2, relevance_score=0.95),
            RerankScoredDocument(index=0, relevance_score=0.75),
            RerankScoredDocument(index=1, relevance_score=0.55),
        ],
    )
    outcome = await rerank_direct_candidates(
        query="test query",
        candidates=candidates,
        settings=_settings_with_rerank_enabled(True),
        client=fake_client,
    )
    assert [item.memory_id for item in outcome.direct_candidates] == ["mem-c", "mem-a", "mem-b"]
    assert [item.normalized_retrieval_score for item in outcome.direct_candidates] == [
        0.95,
        0.75,
        0.55,
    ]
    assert outcome.warnings == []


@pytest.mark.asyncio
async def test_rerank_disabled_is_noop() -> None:
    candidates = [
        _direct("mem-a", normalized_retrieval_score=0.3),
        _direct("mem-b", normalized_retrieval_score=0.2),
    ]
    fake_client = FakeRerankClient()
    outcome = await rerank_direct_candidates(
        query="test query",
        candidates=candidates,
        settings=_settings_with_rerank_enabled(False),
        client=fake_client,
    )
    assert outcome.direct_candidates == candidates
    assert fake_client.calls == []


@pytest.mark.asyncio
async def test_rerank_client_error_returns_warning_and_rrf_order() -> None:
    candidates = [
        _direct("mem-a", normalized_retrieval_score=0.3),
        _direct("mem-b", normalized_retrieval_score=0.2),
    ]
    fake_client = FakeRerankClient(
        error=RerankServiceError(
            code="rerank_failed",
            provider="siliconflow",
            status_code=500,
            trace_id=None,
            sanitized_message="server error",
        ),
    )
    outcome = await rerank_direct_candidates(
        query="test query",
        candidates=candidates,
        settings=_settings_with_rerank_enabled(True),
        client=fake_client,
    )
    assert outcome.direct_candidates == candidates
    assert len(outcome.warnings) == 1
    assert outcome.warnings[0].kind == "rerank_failed"


@pytest.mark.asyncio
async def test_rerank_empty_direct_list_is_noop() -> None:
    fake_client = FakeRerankClient()
    outcome = await rerank_direct_candidates(
        query="test query",
        candidates=[],
        settings=_settings_with_rerank_enabled(True),
        client=fake_client,
    )
    assert outcome.direct_candidates == []
    assert fake_client.calls == []


@pytest.mark.asyncio
async def test_empty_document_candidate_keeps_rrf_position() -> None:
    candidates = [
        _direct("mem-a", normalized_retrieval_score=0.3),
        _direct("mem-b", normalized_retrieval_score=0.2, content=""),
        _direct("mem-c", normalized_retrieval_score=0.1),
    ]
    fake_client = FakeRerankClient(
        results=[
            RerankScoredDocument(index=1, relevance_score=0.9),
            RerankScoredDocument(index=0, relevance_score=0.8),
        ],
    )
    outcome = await rerank_direct_candidates(
        query="test query",
        candidates=candidates,
        settings=_settings_with_rerank_enabled(True),
        client=fake_client,
    )
    assert [item.memory_id for item in outcome.direct_candidates] == ["mem-c", "mem-b", "mem-a"]
    assert outcome.direct_candidates[1].normalized_retrieval_score == 0.2
