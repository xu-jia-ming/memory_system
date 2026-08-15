"""Shared fake helpers for EXT-003 contract and integration tests."""

from __future__ import annotations

import json
from typing import Any


def valid_extraction_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "entities": [
            {
                "local_entity_id": "entity_1",
                "name": "Agent Memory System",
                "type": "project",
                "aliases": ["记忆系统项目"],
            }
        ],
        "memories": [
            {
                "memory_type": "event",
                "content": "用户正在开发 Agent Memory System",
                "subject_entity_id": "user",
                "predicate": "works_on",
                "object_entity_id": "entity_1",
                "object_value": None,
                "event_status": "ongoing",
                "start_time": None,
                "end_time": None,
                "original_time_text": "正在",
                "confidence": 0.95,
                "source_message_ids": ["msg_000001"],
            }
        ],
    }
    payload.update(overrides)
    return payload


def persisted_extraction_payload(**overrides: Any) -> dict[str, Any]:
    """Durable extraction_result shape after EXT-003 application enrichment."""
    payload = valid_extraction_payload(**overrides)
    for memory in payload["memories"]:
        memory.setdefault("candidate_source_time", 1_700_000_000)
        memory.setdefault("candidate_fingerprint", "sha256:ext003-test-fingerprint")
    return payload


def valid_extraction_json(**overrides: Any) -> str:
    return json.dumps(valid_extraction_payload(**overrides))


def empty_extraction_json() -> str:
    return json.dumps({"entities": [], "memories": []})
