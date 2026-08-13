"""Unit tests for retrieval scoring service orchestration (RET-004 U1-U15)."""

from __future__ import annotations

import pytest

from memory_system.domain.models.authoritative_recall import (
    AuthoritativeRecallSuccess,
    InternalRetrievalWarning,
    ValidatedRetrievalCandidate,
)
from memory_system.domain.models.retrieval_memory_snapshot import (
    RetrievalEntitySnapshot,
    RetrievalMemorySnapshot,
)
from memory_system.domain.models.retrieval_scoring import RetrievalScoringQuery
from memory_system.domain.services.evidence_aggregation import EvidenceRow
from memory_system.domain.services.retrieval_scoring_service import RetrievalScoringService
from memory_system.infrastructure.neo4j.retrieval_evidence_read_repository import (
    RetrievalEvidenceReadError,
)
from memory_system.settings import get_settings

USER_ID = "user-a"
SETTINGS = get_settings()


def make_memory_snapshot(
    *,
    memory_id: str = "mem-1",
    status: str = "active",
    importance: float = 0.8,
    confidence: float = 0.9,
    retrieval_count: int = 1,
    latest_source_time: int | None = 150,
) -> RetrievalMemorySnapshot:
    return RetrievalMemorySnapshot(
        memory_id=memory_id,
        user_id=USER_ID,
        memory_type="fact",
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
        confidence=confidence,
        retrieval_count=retrieval_count,
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
        object_entity=None,
    )


def make_validated(
    *,
    memory_id: str = "mem-1",
    candidate_origin: str = "direct",
    normalized_retrieval_score: float | None = 0.8,
    graph_retrieval_score: float | None = None,
    memory: RetrievalMemorySnapshot | None = None,
    rrf_score: float | None = 0.5,
    min_available_rank: int | None = 1,
) -> ValidatedRetrievalCandidate:
    return ValidatedRetrievalCandidate(
        memory_id=memory_id,
        bm25_rank=1,
        vector_rank=None,
        bm25_score=1.5,
        vector_score=None,
        retrieval_source=["bm25"],
        rrf_score=rrf_score,
        min_available_rank=min_available_rank,
        normalized_retrieval_score=normalized_retrieval_score,
        graph_retrieval_score=graph_retrieval_score,
        candidate_origin=candidate_origin,  # type: ignore[arg-type]
        memory=memory or make_memory_snapshot(memory_id=memory_id),
    )


def make_authoritative_success(
    *,
    direct: list[ValidatedRetrievalCandidate] | None = None,
    expanded: list[ValidatedRetrievalCandidate] | None = None,
    warnings: list[InternalRetrievalWarning] | None = None,
    user_id: str = USER_ID,
) -> AuthoritativeRecallSuccess:
    return AuthoritativeRecallSuccess(
        user_id=user_id,
        retrieval_mode="hybrid",
        effective_channel_count=2,
        direct_candidates=direct or [],
        expanded_candidates=expanded or [],
        warnings=warnings or [],
    )


class FakeEvidenceRepo:
    def __init__(
        self,
        *,
        rows: list[EvidenceRow] | None = None,
        fail: bool = False,
    ) -> None:
        self.rows = rows or []
        self.fail = fail
        self.calls: list[tuple[str, list[str]]] = []

    async def load_evidence_for_memories(
        self,
        user_id: str,
        memory_ids: list[str],
    ) -> list[EvidenceRow]:
        self.calls.append((user_id, memory_ids))
        if self.fail:
            raise RetrievalEvidenceReadError("neo4j evidence load failed", retryable=True)
        return [row for row in self.rows if row.memory_id in memory_ids]


def make_service(evidence_repo: FakeEvidenceRepo) -> RetrievalScoringService:
    return RetrievalScoringService(evidence_repo=evidence_repo, settings=SETTINGS)


@pytest.mark.asyncio
async def test_u4_direct_missing_normalized_skipped() -> None:
    repo = FakeEvidenceRepo()
    service = make_service(repo)
    authoritative = make_authoritative_success(
        direct=[
            make_validated(memory_id="skip-me", normalized_retrieval_score=None),
            make_validated(memory_id="keep-me", normalized_retrieval_score=0.9),
        ],
    )
    outcome = await service.score(
        RetrievalScoringQuery(
            authoritative_success=authoritative,
            top_k=10,
            current_time=0,
        )
    )
    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert [m.memory_id for m in outcome.success.scored_memories] == ["keep-me"]
    assert len(repo.calls) == 1


@pytest.mark.asyncio
async def test_u5_expanded_missing_graph_skipped() -> None:
    repo = FakeEvidenceRepo()
    service = make_service(repo)
    authoritative = make_authoritative_success(
        expanded=[
            make_validated(
                memory_id="skip-expanded",
                candidate_origin="expanded",
                normalized_retrieval_score=None,
                graph_retrieval_score=None,
            ),
            make_validated(
                memory_id="keep-expanded",
                candidate_origin="expanded",
                normalized_retrieval_score=None,
                graph_retrieval_score=0.7,
            ),
        ],
    )
    outcome = await service.score(
        RetrievalScoringQuery(
            authoritative_success=authoritative,
            top_k=10,
            current_time=0,
        )
    )
    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert [m.memory_id for m in outcome.success.scored_memories] == ["keep-expanded"]


@pytest.mark.asyncio
async def test_u6_all_skipped_empty_success_no_evidence_call() -> None:
    repo = FakeEvidenceRepo()
    service = make_service(repo)
    authoritative = make_authoritative_success(
        direct=[make_validated(normalized_retrieval_score=None)],
    )
    outcome = await service.score(
        RetrievalScoringQuery(
            authoritative_success=authoritative,
            top_k=10,
            current_time=0,
        )
    )
    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert outcome.success.scored_memories == []
    assert repo.calls == []


@pytest.mark.asyncio
async def test_u7_top_k_truncation() -> None:
    repo = FakeEvidenceRepo()
    service = make_service(repo)
    direct = [
        make_validated(
            memory_id=f"mem-{index}",
            normalized_retrieval_score=0.9 - index * 0.01,
            memory=make_memory_snapshot(
                memory_id=f"mem-{index}",
                importance=0.9 - index * 0.01,
            ),
        )
        for index in range(5)
    ]
    authoritative = make_authoritative_success(direct=direct)
    outcome = await service.score(
        RetrievalScoringQuery(
            authoritative_success=authoritative,
            top_k=3,
            current_time=0,
        )
    )
    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert len(outcome.success.scored_memories) == 3
    assert repo.calls[0][1] == [
        m.memory_id for m in outcome.success.scored_memories
    ]


@pytest.mark.asyncio
async def test_u7b_top_k_greater_than_candidates() -> None:
    repo = FakeEvidenceRepo()
    service = make_service(repo)
    direct = [
        make_validated(memory_id="mem-1", normalized_retrieval_score=0.9),
        make_validated(memory_id="mem-2", normalized_retrieval_score=0.8),
    ]
    authoritative = make_authoritative_success(direct=direct)
    outcome = await service.score(
        RetrievalScoringQuery(
            authoritative_success=authoritative,
            top_k=10,
            current_time=0,
        )
    )
    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert len(outcome.success.scored_memories) == 2
    assert repo.calls[0][1] == ["mem-1", "mem-2"]


@pytest.mark.asyncio
async def test_u8_evidence_repo_receives_user_id() -> None:
    repo = FakeEvidenceRepo()
    service = make_service(repo)
    authoritative = make_authoritative_success(
        direct=[make_validated(memory_id="mem-1")],
        user_id="user-bound",
    )
    await service.score(
        RetrievalScoringQuery(
            authoritative_success=authoritative,
            top_k=5,
            current_time=0,
        )
    )
    assert repo.calls[0][0] == "user-bound"


@pytest.mark.asyncio
async def test_u9_status_penalties_applied() -> None:
    repo = FakeEvidenceRepo()
    service = make_service(repo)
    shared_importance = 0.6
    shared_confidence = 0.9
    authoritative = make_authoritative_success(
        direct=[
            make_validated(
                memory_id="active",
                normalized_retrieval_score=0.8,
                memory=make_memory_snapshot(
                    memory_id="active",
                    status="active",
                    importance=shared_importance,
                    confidence=shared_confidence,
                    retrieval_count=0,
                    latest_source_time=None,
                ),
            ),
            make_validated(
                memory_id="conflicted",
                normalized_retrieval_score=0.8,
                memory=make_memory_snapshot(
                    memory_id="conflicted",
                    status="conflicted",
                    importance=shared_importance,
                    confidence=shared_confidence,
                    retrieval_count=0,
                    latest_source_time=None,
                ),
            ),
            make_validated(
                memory_id="superseded",
                normalized_retrieval_score=0.8,
                memory=make_memory_snapshot(
                    memory_id="superseded",
                    status="superseded",
                    importance=shared_importance,
                    confidence=shared_confidence,
                    retrieval_count=0,
                    latest_source_time=None,
                ),
            ),
        ],
    )
    outcome = await service.score(
        RetrievalScoringQuery(
            authoritative_success=authoritative,
            top_k=10,
            current_time=0,
        )
    )
    assert outcome.outcome == "success"
    assert outcome.success is not None
    by_id = {m.memory_id: m.final_score for m in outcome.success.scored_memories}
    active_score = by_id["active"]
    assert by_id["conflicted"] == pytest.approx(active_score * 0.85, abs=1e-6)
    assert by_id["superseded"] == pytest.approx(active_score * 0.60, abs=1e-6)


@pytest.mark.asyncio
async def test_u10_warnings_passthrough() -> None:
    repo = FakeEvidenceRepo()
    service = make_service(repo)
    warnings = [
        InternalRetrievalWarning(kind="dirty_index_document", memory_id="mem-1"),
        InternalRetrievalWarning(kind="graph_expansion_failed", memory_id=None),
    ]
    authoritative = make_authoritative_success(
        direct=[make_validated()],
        warnings=warnings,
    )
    outcome = await service.score(
        RetrievalScoringQuery(
            authoritative_success=authoritative,
            top_k=5,
            current_time=0,
        )
    )
    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert outcome.success.warnings == warnings


def test_u11_upstream_failure_is_caller_responsibility() -> None:
    """Service accepts only AuthoritativeRecallSuccess, not upstream failure outcomes."""
    query_fields = RetrievalScoringQuery.model_fields
    assert "authoritative_success" in query_fields
    assert query_fields["authoritative_success"].annotation is AuthoritativeRecallSuccess


@pytest.mark.asyncio
async def test_u12_evidence_repo_failure_graph_load_failed() -> None:
    repo = FakeEvidenceRepo(fail=True)
    service = make_service(repo)
    authoritative = make_authoritative_success(direct=[make_validated()])
    outcome = await service.score(
        RetrievalScoringQuery(
            authoritative_success=authoritative,
            top_k=5,
            current_time=0,
        )
    )
    assert outcome.outcome == "failure"
    assert outcome.failure is not None
    assert outcome.failure.kind == "graph_load_failed"
    assert outcome.success is None


@pytest.mark.asyncio
async def test_u13_empty_top_k_skips_evidence_repo() -> None:
    repo = FakeEvidenceRepo()
    service = make_service(repo)
    authoritative = make_authoritative_success()
    outcome = await service.score(
        RetrievalScoringQuery(
            authoritative_success=authoritative,
            top_k=5,
            current_time=0,
        )
    )
    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert outcome.success.scored_memories == []
    assert repo.calls == []


@pytest.mark.asyncio
async def test_u14_injectable_current_time() -> None:
    repo = FakeEvidenceRepo()
    service = make_service(repo)
    memory = make_memory_snapshot(
        memory_id="mem-1",
        latest_source_time=86400,
        retrieval_count=0,
    )
    authoritative = make_authoritative_success(
        direct=[make_validated(memory_id="mem-1", memory=memory)],
    )
    outcome_recent = await service.score(
        RetrievalScoringQuery(
            authoritative_success=authoritative,
            top_k=5,
            current_time=86400,
        )
    )
    outcome_old = await service.score(
        RetrievalScoringQuery(
            authoritative_success=authoritative,
            top_k=5,
            current_time=86400 * 60,
        )
    )
    assert outcome_recent.outcome == "success"
    assert outcome_old.outcome == "success"
    assert outcome_recent.success is not None
    assert outcome_old.success is not None
    recent_score = outcome_recent.success.scored_memories[0].final_score
    old_score = outcome_old.success.scored_memories[0].final_score
    assert recent_score > old_score


@pytest.mark.asyncio
async def test_evidence_aggregation_attached_to_scored_memory() -> None:
    repo = FakeEvidenceRepo(
        rows=[
            EvidenceRow("e1", "mem-1", 200, ["m3"]),
            EvidenceRow("e2", "mem-1", 100, ["m1"]),
        ],
    )
    service = make_service(repo)
    authoritative = make_authoritative_success(direct=[make_validated(memory_id="mem-1")])
    outcome = await service.score(
        RetrievalScoringQuery(
            authoritative_success=authoritative,
            top_k=5,
            current_time=0,
        )
    )
    assert outcome.outcome == "success"
    assert outcome.success is not None
    scored = outcome.success.scored_memories[0]
    assert scored.evidence_count == 2
    assert scored.source_message_ids == ["m3", "m1"]


@pytest.mark.asyncio
async def test_zero_evidence_success() -> None:
    repo = FakeEvidenceRepo(rows=[])
    service = make_service(repo)
    authoritative = make_authoritative_success(direct=[make_validated(memory_id="mem-1")])
    outcome = await service.score(
        RetrievalScoringQuery(
            authoritative_success=authoritative,
            top_k=5,
            current_time=0,
        )
    )
    assert outcome.outcome == "success"
    assert outcome.success is not None
    scored = outcome.success.scored_memories[0]
    assert scored.evidence_count == 0
    assert scored.source_message_ids == []


@pytest.mark.asyncio
async def test_sf2_rrf_fields_passthrough() -> None:
    repo = FakeEvidenceRepo()
    service = make_service(repo)
    authoritative = make_authoritative_success(
        direct=[
            make_validated(
                memory_id="mem-1",
                rrf_score=0.123,
                min_available_rank=2,
            ),
        ],
    )
    outcome = await service.score(
        RetrievalScoringQuery(
            authoritative_success=authoritative,
            top_k=5,
            current_time=0,
        )
    )
    assert outcome.outcome == "success"
    assert outcome.success is not None
    scored = outcome.success.scored_memories[0]
    assert scored.rrf_score == 0.123
    assert scored.min_available_rank == 2


@pytest.mark.asyncio
async def test_invalid_top_k_raises() -> None:
    repo = FakeEvidenceRepo()
    service = make_service(repo)
    authoritative = make_authoritative_success(direct=[make_validated()])
    with pytest.raises(ValueError, match="top_k"):
        await service.score(
            RetrievalScoringQuery(
                authoritative_success=authoritative,
                top_k=SETTINGS.memory_retrieval.max_top_k + 1,
                current_time=0,
            )
        )


@pytest.mark.asyncio
async def test_merge_direct_then_expanded() -> None:
    repo = FakeEvidenceRepo()
    service = make_service(repo)
    authoritative = make_authoritative_success(
        direct=[make_validated(memory_id="direct-1", normalized_retrieval_score=0.95)],
        expanded=[
            make_validated(
                memory_id="expanded-1",
                candidate_origin="expanded",
                normalized_retrieval_score=None,
                graph_retrieval_score=0.85,
            ),
        ],
    )
    outcome = await service.score(
        RetrievalScoringQuery(
            authoritative_success=authoritative,
            top_k=10,
            current_time=0,
        )
    )
    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert {m.memory_id for m in outcome.success.scored_memories} == {
        "direct-1",
        "expanded-1",
    }
