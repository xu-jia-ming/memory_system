"""Unit tests for retrieval memory read repository (RET-003 C3/C5)."""

from __future__ import annotations

from typing import Any

from memory_system.infrastructure.neo4j.retrieval_memory_read_repository import (
    authorized_read_cypher_queries,
    expansion_edge_from_record,
    snapshot_from_record,
)


class FakeRecord:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def data(self) -> dict[str, Any]:
        return self._data


def test_c3_and_c5_authorized_cypher_queries_include_user_id() -> None:
    for query in authorized_read_cypher_queries():
        upper = query.upper()
        assert "$USER_ID" in upper or "USER_ID" in upper
        assert "MATCH" in upper


def test_snapshot_from_record_maps_memory_and_entities() -> None:
    record = FakeRecord(
        {
            "memory_id": "mem-1",
            "user_id": "user-a",
            "memory_type": "fact",
            "status": "active",
            "content": "hello",
            "subject_entity_id": "ent-subject",
            "predicate": "works_on",
            "object_entity_id": "ent-object",
            "object_value": None,
            "event_status": None,
            "start_time": None,
            "end_time": None,
            "original_time_text": None,
            "importance": 0.8,
            "confidence": 0.9,
            "retrieval_count": 1,
            "last_retrieved_time": None,
            "latest_source_time": 100,
            "updated_time": 1_700_000_000,
            "subject_entity_node_id": "ent-subject",
            "subject_canonical_name": "Subject",
            "subject_aliases": ["sub"],
            "subject_entity_type": "concept",
            "subject_normalized_name": "subject",
            "object_entity_node_id": None,
            "object_canonical_name": None,
            "object_aliases": None,
            "object_entity_type": None,
            "object_normalized_name": None,
        },
    )
    snapshot = snapshot_from_record(record)
    assert snapshot.memory_id == "mem-1"
    assert snapshot.subject_entity is not None
    assert snapshot.subject_entity.aliases == ["sub"]
    assert snapshot.object_entity is None


def test_expansion_edge_from_record() -> None:
    record = FakeRecord(
        {
            "seed_id": "seed-1",
            "related_id": "rel-1",
            "expansion_tier": 0,
            "importance": 0.7,
            "latest_source_time": 50,
            "memory_type": "fact",
            "status": "active",
        },
    )
    edge = expansion_edge_from_record(record)
    assert edge.seed_id == "seed-1"
    assert edge.related_id == "rel-1"
    assert edge.expansion_tier == 0
