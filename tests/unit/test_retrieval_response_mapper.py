"""Unit tests for retrieval response mapper (RET-005 §6)."""

from __future__ import annotations

import pytest

from memory_system.domain.models.authoritative_recall import CandidateOrigin, RetrievalSource
from memory_system.domain.models.retrieval_memory_snapshot import RetrievalEntitySnapshot
from memory_system.domain.models.retrieval_scoring import ActRScoreComponents, ScoredRetrievalMemory
from memory_system.domain.services.retrieval_response_mapper import (
    MappedRetrievalObject,
    MissingSubjectEntityError,
    map_scored_memory_to_response_item,
)


def _components() -> ActRScoreComponents:
    return ActRScoreComponents(
        retrieval_score=0.8,
        importance_score=0.7,
        confidence_score=0.6,
        frequency_score=0.5,
        recency_score=0.4,
    )


def test_maps_entity_object() -> None:
    scored = ScoredRetrievalMemory(
        memory_id="mem-1",
        memory_type="fact",
        status="active",
        content="hello",
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
        predicate="works_on",
        object_value=None,
        event_status=None,
        start_time=None,
        end_time=None,
        confidence=0.9,
        importance=0.8,
        latest_source_time=100,
        retrieval_source=["bm25", "vector"],
        bm25_rank=1,
        vector_rank=2,
        bm25_score=1.2,
        vector_score=0.9,
        rrf_score=0.5,
        min_available_rank=1,
        candidate_origin="direct",
        act_r_components=_components(),
        final_score=0.123456,
        evidence_count=2,
        source_message_ids=["msg-1"],
    )
    item = map_scored_memory_to_response_item(scored)
    assert item.score == 0.123456
    assert item.subject.entity_id == "ent-subject"
    assert item.object.entity_id == "ent-object"
    assert item.object.value is None


def test_maps_literal_object_value() -> None:
    scored = ScoredRetrievalMemory(
        memory_id="mem-2",
        memory_type="fact",
        status="active",
        content="hello",
        subject_entity=RetrievalEntitySnapshot(
            entity_id="ent-subject",
            canonical_name="Subject",
            aliases=[],
            entity_type="concept",
            normalized_name="subject",
        ),
        object_entity=None,
        predicate="has_value",
        object_value="literal",
        event_status=None,
        start_time=None,
        end_time=None,
        confidence=0.9,
        importance=0.8,
        latest_source_time=None,
        retrieval_source=["bm25"],
        bm25_rank=1,
        vector_rank=None,
        bm25_score=1.0,
        vector_score=None,
        rrf_score=0.4,
        min_available_rank=1,
        candidate_origin="direct",
        act_r_components=_components(),
        final_score=0.5,
        evidence_count=0,
        source_message_ids=[],
    )
    item = map_scored_memory_to_response_item(scored)
    assert item.object == MappedRetrievalObject(entity_id=None, name=None, value="literal")


def test_missing_subject_raises() -> None:
    scored = ScoredRetrievalMemory(
        memory_id="mem-3",
        memory_type="fact",
        status="active",
        content="hello",
        subject_entity=None,
        object_entity=None,
        predicate="p",
        object_value=None,
        event_status=None,
        start_time=None,
        end_time=None,
        confidence=0.9,
        importance=0.8,
        latest_source_time=None,
        retrieval_source=["bm25"],
        bm25_rank=1,
        vector_rank=None,
        bm25_score=1.0,
        vector_score=None,
        rrf_score=0.4,
        min_available_rank=1,
        candidate_origin="direct",
        act_r_components=_components(),
        final_score=0.5,
        evidence_count=0,
        source_message_ids=[],
    )
    with pytest.raises(MissingSubjectEntityError):
        map_scored_memory_to_response_item(scored)
