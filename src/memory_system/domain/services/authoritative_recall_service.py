"""RET-003 authoritative recall orchestration: Neo4j readback, graph expansion, ES MGET."""

from __future__ import annotations

from typing import Protocol

from elasticsearch import AsyncElasticsearch
from neo4j import AsyncDriver

from memory_system.domain.models.authoritative_recall import (
    AuthoritativeRecallFailure,
    AuthoritativeRecallOutcome,
    AuthoritativeRecallQuery,
    AuthoritativeRecallSuccess,
    InternalRetrievalWarning,
    ValidatedRetrievalCandidate,
)
from memory_system.domain.models.hybrid_retrieval import FusedRetrievalCandidate
from memory_system.domain.models.retrieval_memory_snapshot import RetrievalMemorySnapshot
from memory_system.domain.services.graph_expansion_ranker import (
    AggregatedExpansionCandidate,
    ExpansionEdge,
    aggregate_expanded_candidates,
    dedupe_rrf_candidates,
    expanded_candidate_sort_key,
    merge_overlap_with_direct,
    rank_per_seed_edges,
)
from memory_system.domain.services.retrieval_memory_validator import (
    normalize_memory_types,
    validate_memory_for_request,
)
from memory_system.infrastructure.elasticsearch.mget_retrieval_repository import (
    MgetRetrievalError,
    MgetRetrievalRepository,
)
from memory_system.infrastructure.neo4j.retrieval_memory_read_repository import (
    RetrievalMemoryReadError,
    RetrievalMemoryReadRepository,
)
from memory_system.settings.models import Settings


class RetrievalMemoryReadPort(Protocol):
    async def load_memories(
        self,
        user_id: str,
        memory_ids: list[str],
    ) -> dict[str, RetrievalMemorySnapshot]: ...

    async def expand_one_hop(
        self,
        user_id: str,
        seed_ids: list[str],
    ) -> list[ExpansionEdge]: ...


class MgetRetrievalPort(Protocol):
    async def exists_many(
        self,
        *,
        index_name: str,
        memory_ids: list[str],
        request_timeout: float,
    ) -> set[str]: ...


class AuthoritativeRecallService:
    """Neo4j authoritative readback with optional one-hop graph expansion and ES MGET."""

    def __init__(
        self,
        neo4j_repo: RetrievalMemoryReadPort,
        mget_repo: MgetRetrievalPort,
        *,
        settings: Settings,
    ) -> None:
        self._neo4j_repo = neo4j_repo
        self._mget_repo = mget_repo
        self._settings = settings

    async def recall(self, query: AuthoritativeRecallQuery) -> AuthoritativeRecallOutcome:
        memory_types = normalize_memory_types(query.memory_types)
        hybrid = query.hybrid_success
        user_id = hybrid.user_id
        if not user_id:
            raise ValueError("hybrid_success.user_id must be non-empty")

        if not hybrid.candidates:
            return self._success(query, direct_candidates=[], expanded_candidates=[], warnings=[])

        deduped = dedupe_rrf_candidates(hybrid.candidates)
        es_hit_ids = {candidate.memory_id for candidate in deduped}

        try:
            seed_snapshots = await self._neo4j_repo.load_memories(
                user_id,
                sorted({candidate.memory_id for candidate in deduped}),
            )
        except RetrievalMemoryReadError as exc:
            return AuthoritativeRecallOutcome(
                outcome="failure",
                failure=AuthoritativeRecallFailure(message=str(exc)),
            )

        direct_candidates, warnings = self._build_direct_candidates(
            deduped=deduped,
            snapshots=seed_snapshots,
            user_id=user_id,
            memory_types=memory_types,
            include_conflicted=query.include_conflicted,
            include_history=query.include_history,
            es_hit_ids=es_hit_ids,
        )

        expanded_candidates: list[ValidatedRetrievalCandidate] = []
        if query.graph_expand and direct_candidates:
            (
                direct_candidates,
                expanded_candidates,
                expansion_warnings,
            ) = await self._expand_candidates(
                query=query,
                memory_types=memory_types,
                direct_candidates=direct_candidates,
            )
            warnings.extend(expansion_warnings)

        return self._success(
            query,
            direct_candidates=direct_candidates,
            expanded_candidates=expanded_candidates,
            warnings=warnings,
        )

    def _build_direct_candidates(
        self,
        *,
        deduped: list[FusedRetrievalCandidate],
        snapshots: dict[str, RetrievalMemorySnapshot],
        user_id: str,
        memory_types: list[str] | None,
        include_conflicted: bool,
        include_history: bool,
        es_hit_ids: set[str],
    ) -> tuple[list[ValidatedRetrievalCandidate], list[InternalRetrievalWarning]]:
        direct_candidates: list[ValidatedRetrievalCandidate] = []
        warnings: list[InternalRetrievalWarning] = []

        for fused in deduped:
            snapshot = snapshots.get(fused.memory_id)
            if snapshot is None:
                warnings.append(
                    InternalRetrievalWarning(
                        kind="dirty_index_document",
                        memory_id=fused.memory_id,
                    ),
                )
                continue

            validation = validate_memory_for_request(
                snapshot,
                user_id,
                memory_types,
                include_conflicted=include_conflicted,
                include_history=include_history,
            )
            if not validation.valid:
                if (
                    validation.rejection_reason == "type_or_status"
                    and fused.memory_id in es_hit_ids
                ):
                    warnings.append(
                        InternalRetrievalWarning(
                            kind="stale_index_document",
                            memory_id=fused.memory_id,
                        ),
                    )
                continue

            direct_candidates.append(
                ValidatedRetrievalCandidate(
                    memory_id=fused.memory_id,
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
                    memory=snapshot,
                ),
            )
        return direct_candidates, warnings

    async def _expand_candidates(
        self,
        *,
        query: AuthoritativeRecallQuery,
        memory_types: list[str] | None,
        direct_candidates: list[ValidatedRetrievalCandidate],
    ) -> tuple[
        list[ValidatedRetrievalCandidate],
        list[ValidatedRetrievalCandidate],
        list[InternalRetrievalWarning],
    ]:
        settings = self._settings.memory_retrieval
        user_id = query.hybrid_success.user_id
        warnings: list[InternalRetrievalWarning] = []

        try:
            raw_edges = await self._neo4j_repo.expand_one_hop(
                user_id,
                sorted(candidate.memory_id for candidate in direct_candidates),
            )
        except RetrievalMemoryReadError:
            warnings.append(InternalRetrievalWarning(kind="graph_expansion_failed"))
            return direct_candidates, [], warnings

        filtered_edges = self._filter_expansion_edges(
            raw_edges,
            user_id=user_id,
            memory_types=memory_types,
            include_conflicted=query.include_conflicted,
            include_history=query.include_history,
        )
        per_seed_edges = rank_per_seed_edges(
            filtered_edges,
            per_seed_limit=settings.graph_expand_per_seed,
        )
        seed_scores = {
            candidate.memory_id: candidate.normalized_retrieval_score
            for candidate in direct_candidates
        }
        aggregated = aggregate_expanded_candidates(
            per_seed_edges,
            seed_scores=seed_scores,
            max_graph_candidates=settings.max_graph_candidates,
            graph_decay=settings.graph_decay,
        )
        direct_candidates, pure_expanded = merge_overlap_with_direct(direct_candidates, aggregated)
        if not pure_expanded:
            return direct_candidates, [], warnings

        pure_expanded.sort(key=expanded_candidate_sort_key)
        pure_ids = sorted(item.related_id for item in pure_expanded)

        try:
            expanded_snapshots = await self._neo4j_repo.load_memories(user_id, pure_ids)
        except RetrievalMemoryReadError:
            warnings.append(InternalRetrievalWarning(kind="graph_expansion_failed"))
            return direct_candidates, [], warnings

        validated_pure: list[tuple[AggregatedExpansionCandidate, RetrievalMemorySnapshot]] = []
        for item in pure_expanded:
            snapshot = expanded_snapshots.get(item.related_id)
            if snapshot is None:
                continue
            validation = validate_memory_for_request(
                snapshot,
                user_id,
                memory_types,
                include_conflicted=query.include_conflicted,
                include_history=query.include_history,
            )
            if not validation.valid:
                continue
            validated_pure.append((item, snapshot))

        if not validated_pure:
            return direct_candidates, [], warnings

        try:
            found_ids = await self._mget_repo.exists_many(
                index_name=settings.index_name,
                memory_ids=[item.related_id for item, _ in validated_pure],
                request_timeout=float(settings.elasticsearch_timeout_seconds),
            )
        except MgetRetrievalError:
            warnings.append(InternalRetrievalWarning(kind="graph_expansion_failed"))
            return direct_candidates, [], warnings

        expanded_candidates: list[ValidatedRetrievalCandidate] = []
        for item, snapshot in validated_pure:
            if item.related_id not in found_ids:
                continue
            expanded_candidates.append(
                ValidatedRetrievalCandidate(
                    memory_id=item.related_id,
                    bm25_rank=None,
                    vector_rank=None,
                    bm25_score=None,
                    vector_score=None,
                    retrieval_source=["graph"],
                    rrf_score=None,
                    min_available_rank=None,
                    normalized_retrieval_score=None,
                    graph_retrieval_score=item.graph_retrieval_score,
                    candidate_origin="expanded",
                    memory=snapshot,
                ),
            )
        return direct_candidates, expanded_candidates, warnings

    def _filter_expansion_edges(
        self,
        edges: list[ExpansionEdge],
        *,
        user_id: str,
        memory_types: list[str] | None,
        include_conflicted: bool,
        include_history: bool,
    ) -> list[ExpansionEdge]:
        filtered: list[ExpansionEdge] = []
        for edge in edges:
            snapshot = RetrievalMemorySnapshot(
                memory_id=edge.related_id,
                user_id=user_id,
                memory_type=edge.memory_type,
                status=edge.status,
                content="",
                subject_entity_id="",
                predicate="",
                object_entity_id=None,
                object_value=None,
                event_status=None,
                start_time=None,
                end_time=None,
                original_time_text=None,
                importance=edge.importance,
                confidence=0.0,
                retrieval_count=0,
                last_retrieved_time=None,
                latest_source_time=edge.latest_source_time,
                updated_time=0,
                subject_entity=None,
                object_entity=None,
            )
            validation = validate_memory_for_request(
                snapshot,
                user_id,
                memory_types,
                include_conflicted=include_conflicted,
                include_history=include_history,
            )
            if validation.valid:
                filtered.append(edge)
        return filtered

    def _success(
        self,
        query: AuthoritativeRecallQuery,
        *,
        direct_candidates: list[ValidatedRetrievalCandidate],
        expanded_candidates: list[ValidatedRetrievalCandidate],
        warnings: list[InternalRetrievalWarning],
    ) -> AuthoritativeRecallOutcome:
        hybrid = query.hybrid_success
        return AuthoritativeRecallOutcome(
            outcome="success",
            success=AuthoritativeRecallSuccess(
                user_id=hybrid.user_id,
                retrieval_mode=hybrid.retrieval_mode,
                effective_channel_count=hybrid.effective_channel_count,
                direct_candidates=direct_candidates,
                expanded_candidates=expanded_candidates,
                warnings=warnings,
            ),
        )


def create_authoritative_recall_service(
    *,
    neo4j_driver: AsyncDriver,
    es_client: AsyncElasticsearch,
    settings: Settings,
) -> AuthoritativeRecallService:
    retrieval_settings = settings.memory_retrieval
    neo4j_repo = RetrievalMemoryReadRepository(
        neo4j_driver,
        neo4j_timeout_seconds=float(retrieval_settings.neo4j_timeout_seconds),
    )
    mget_repo = MgetRetrievalRepository(es_client)
    return AuthoritativeRecallService(
        neo4j_repo=neo4j_repo,
        mget_repo=mget_repo,
        settings=settings,
    )
