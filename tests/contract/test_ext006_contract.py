"""Contract tests for EXT-006 graph write."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import get_type_hints

from memory_system.domain.models.graph_write import (
    GraphWriteErrorCode,
    GraphWriteFailure,
    GraphWriteInput,
    GraphWriteOutcome,
    GraphWriteSuccess,
    IndexSyncMemoryEntry,
)
from memory_system.domain.services.entity_alignment_service import EntityAlignmentService
from memory_system.domain.services.extraction_llm_service import ExtractionLlmService
from memory_system.domain.services.extraction_pipeline_port import PipelineTerminalDecision
from memory_system.domain.services.graph_write_service import GraphWriteService
from memory_system.domain.services.reconciliation_service import ReconciliationService
from memory_system.entrypoints import extraction_worker
from memory_system.infrastructure.neo4j.graph_write_repository import (
    authorized_write_cypher_queries,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"


def test_c1_input_contract_fields() -> None:
    hints = get_type_hints(GraphWriteInput)
    assert set(hints) == {
        "task_id",
        "archive_id",
        "user_id",
        "session_id",
        "extraction_result",
        "entity_alignment",
        "reconciliation",
    }


def test_c2_output_shapes_extra_forbid() -> None:
    assert set(GraphWriteOutcome.model_fields) == {"outcome", "success", "failure"}
    assert set(GraphWriteSuccess.model_fields) == {
        "user_id",
        "archive_id",
        "skipped_graph_write",
        "index_sync_memory_set",
    }
    assert set(IndexSyncMemoryEntry.model_fields) == {
        "memory_id",
        "core_search_text",
        "token_count",
    }
    assert GraphWriteOutcome.model_config.get("extra") == "forbid"


def test_c3_error_code_whitelist() -> None:
    allowed = {item.value for item in GraphWriteErrorCode}
    assert allowed == {"graph_write_failed", "memory_search_text_too_long"}
    forbidden = {
        "entity_alignment_failed",
        "graph_query_failed",
        "reconciliation_plan_conflict",
        "llm_timeout",
        "archive_not_found",
        "retrieval_index_write_failed",
    }
    assert forbidden.isdisjoint(allowed)


def test_c4_failed_stage_literal() -> None:
    hints = get_type_hints(GraphWriteFailure)
    assert hints["failed_stage"].__args__ == ("graph_write",)


def test_c5_no_persistence_surface() -> None:
    assert not hasattr(GraphWriteOutcome, "to_durable_dict")


def test_c6_write_cypher_authorization() -> None:
    for query in authorized_write_cypher_queries():
        upper = query.upper()
        for forbidden in ("DELETE", "REMOVE", "DETACH"):
            assert forbidden not in upper
        assert "USER_ID" in upper
        assert "MERGE" in upper or "SET" in upper


def test_c7_no_ext007_plus_behavior() -> None:
    assert "search_text" not in GraphWriteSuccess.model_fields
    assert "embedding" not in GraphWriteSuccess.model_fields


def test_c8_upstream_zero_change() -> None:
    assert inspect.isclass(PipelineTerminalDecision)
    assert inspect.isclass(ExtractionLlmService)
    assert inspect.isclass(EntityAlignmentService)
    assert inspect.isclass(ReconciliationService)
    assert inspect.isclass(GraphWriteService)
    assert hasattr(extraction_worker, "main")


def test_c9_migration_dependency_zero_change() -> None:
    before = PYPROJECT.read_text(encoding="utf-8")
    assert "neo4j>=" in before
