"""Map ScoredRetrievalMemory to HTTP RetrievalMemoryItem (§2.2.12)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from memory_system.domain.models.retrieval_scoring import ScoredRetrievalMemory


class MissingSubjectEntityError(Exception):
    """Raised when a Top-K memory lacks subject_entity (fail-closed)."""


@dataclass(frozen=True)
class MappedRetrievalSubject:
    entity_id: str
    name: str


@dataclass(frozen=True)
class MappedRetrievalObject:
    entity_id: str | None
    name: str | None
    value: str | None


@dataclass(frozen=True)
class MappedRetrievalMemoryItem:
    memory_id: str
    memory_type: str
    content: str
    subject: MappedRetrievalSubject
    predicate: str
    object: MappedRetrievalObject
    status: str
    event_status: str | None
    start_time: int | None
    end_time: int | None
    confidence: float
    importance: float
    latest_source_time: int | None
    score: float
    retrieval_source: list[Literal["bm25", "vector", "graph"]]
    source_message_ids: list[str]
    evidence_count: int


def map_scored_memory_to_response_item(scored: ScoredRetrievalMemory) -> MappedRetrievalMemoryItem:
    if scored.subject_entity is None:
        raise MissingSubjectEntityError(
            f"memory {scored.memory_id!r} missing subject_entity in Top-K response"
        )

    subject = MappedRetrievalSubject(
        entity_id=scored.subject_entity.entity_id,
        name=scored.subject_entity.canonical_name,
    )
    obj = _map_object(scored)

    return MappedRetrievalMemoryItem(
        memory_id=scored.memory_id,
        memory_type=scored.memory_type,
        content=scored.content,
        subject=subject,
        predicate=scored.predicate,
        object=obj,
        status=scored.status,
        event_status=scored.event_status,
        start_time=scored.start_time,
        end_time=scored.end_time,
        confidence=scored.confidence,
        importance=scored.importance,
        latest_source_time=scored.latest_source_time,
        score=scored.final_score,
        retrieval_source=list(scored.retrieval_source),
        source_message_ids=list(scored.source_message_ids),
        evidence_count=scored.evidence_count,
    )


def map_scored_memories_to_response_items(
    scored_memories: list[ScoredRetrievalMemory],
) -> list[MappedRetrievalMemoryItem]:
    return [map_scored_memory_to_response_item(scored) for scored in scored_memories]


def _map_object(scored: ScoredRetrievalMemory) -> MappedRetrievalObject:
    if scored.object_entity is not None:
        return MappedRetrievalObject(
            entity_id=scored.object_entity.entity_id,
            name=scored.object_entity.canonical_name,
            value=None,
        )
    if scored.object_value is not None:
        return MappedRetrievalObject(
            entity_id=None,
            name=None,
            value=scored.object_value,
        )
    return MappedRetrievalObject(entity_id=None, name=None, value=None)
