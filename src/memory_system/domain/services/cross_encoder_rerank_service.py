"""Cross-Encoder rerank domain service for direct retrieval candidates."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from memory_system.domain.models.authoritative_recall import (
    InternalRetrievalWarning,
    ValidatedRetrievalCandidate,
)
from memory_system.infrastructure.rerank.errors import RerankServiceError
from memory_system.infrastructure.rerank.types import RerankClient
from memory_system.settings.models import Settings

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RerankOutcome:
    direct_candidates: list[ValidatedRetrievalCandidate]
    warnings: list[InternalRetrievalWarning]


def _document_text_for_rerank(
    candidate: ValidatedRetrievalCandidate,
    *,
    max_chars: int,
) -> str | None:
    memory = candidate.memory
    search_text = getattr(memory, "search_text", None)
    if isinstance(search_text, str) and search_text.strip():
        text = search_text.strip()
    elif memory.content.strip():
        text = memory.content.strip()
    else:
        return None
    if len(text) > max_chars:
        return text[:max_chars]
    return text


async def rerank_direct_candidates(
    *,
    query: str,
    candidates: list[ValidatedRetrievalCandidate],
    settings: Settings,
    client: RerankClient,
) -> RerankOutcome:
    """Rerank direct candidates or return them unchanged on disable/failure."""
    retrieval = settings.memory_retrieval
    if not retrieval.rerank_enabled or not candidates:
        return RerankOutcome(direct_candidates=list(candidates), warnings=[])

    max_chars = retrieval.embedding_max_input_tokens
    indexed_candidates: list[tuple[int, ValidatedRetrievalCandidate, str]] = []
    for position, candidate in enumerate(candidates):
        document = _document_text_for_rerank(candidate, max_chars=max_chars)
        if document is None:
            _logger.debug(
                "rerank skip empty document memory_id=%s position=%s",
                candidate.memory_id,
                position,
            )
            continue
        indexed_candidates.append((position, candidate, document))

    if not indexed_candidates:
        return RerankOutcome(direct_candidates=list(candidates), warnings=[])

    documents = [document for _, _, document in indexed_candidates]
    top_n = min(retrieval.rerank_top_n, len(documents))

    try:
        rerank_result = await client.rerank(query=query, documents=documents, top_n=top_n)
    except RerankServiceError:
        return RerankOutcome(
            direct_candidates=list(candidates),
            warnings=[InternalRetrievalWarning(kind="rerank_failed")],
        )

    expected_indices = set(range(len(documents)))
    returned_indices = {item.index for item in rerank_result.results}
    if not rerank_result.results or returned_indices != expected_indices:
        return RerankOutcome(
            direct_candidates=list(candidates),
            warnings=[InternalRetrievalWarning(kind="rerank_failed")],
        )

    rerankable_positions = {position for position, _, _ in indexed_candidates}
    score_by_position = {
        indexed_candidates[item.index][0]: item.relevance_score
        for item in rerank_result.results
    }
    reranked_positions = [indexed_candidates[item.index][0] for item in rerank_result.results]
    reranked_iter = iter(reranked_positions)

    output: list[ValidatedRetrievalCandidate] = []
    for position, candidate in enumerate(candidates):
        if position not in rerankable_positions:
            output.append(candidate)
            continue
        source_position = next(reranked_iter)
        source_candidate = candidates[source_position]
        output.append(
            source_candidate.model_copy(
                update={"normalized_retrieval_score": score_by_position[source_position]},
            ),
        )

    return RerankOutcome(direct_candidates=output, warnings=[])
