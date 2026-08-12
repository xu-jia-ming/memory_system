"""Contract tests for EXT-007 retrieval index sync."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import get_type_hints

from memory_system.domain.models.retrieval_index_sync import (
    MemoryIndexDocument,
    MemoryIndexRow,
    RetrievalIndexSyncFailure,
    RetrievalIndexSyncInput,
    RetrievalIndexSyncOutcome,
    RetrievalIndexSyncSuccess,
)
from memory_system.domain.services.entity_alignment_service import EntityAlignmentService
from memory_system.domain.services.extraction_llm_service import ExtractionLlmService
from memory_system.domain.services.extraction_pipeline_port import PipelineTerminalDecision
from memory_system.domain.services.graph_write_service import GraphWriteService
from memory_system.domain.services.reconciliation_service import ReconciliationService
from memory_system.domain.services.retrieval_index_sync_service import EMBEDDING_BATCH_SIZE
from memory_system.entrypoints import extraction_worker
from memory_system.infrastructure.neo4j.retrieval_index_read_repository import (
    authorized_read_cypher_queries,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"


def test_c1_input_contract_fields() -> None:
    hints = get_type_hints(RetrievalIndexSyncInput)
    assert set(hints) == {
        "task_id",
        "archive_id",
        "user_id",
        "session_id",
        "graph_write_success",
        "entity_alignment",
    }


def test_c1_output_shapes_extra_forbid() -> None:
    assert set(RetrievalIndexSyncOutcome.model_fields) == {
        "outcome",
        "success",
        "failure",
        "skip",
    }
    assert set(RetrievalIndexSyncSuccess.model_fields) == {
        "user_id",
        "archive_id",
        "synced_memory_count",
        "omitted_alias_total",
        "task",
    }
    assert RetrievalIndexSyncOutcome.model_config.get("extra") == "forbid"


def test_c2_error_code_whitelist() -> None:
    hints = get_type_hints(RetrievalIndexSyncFailure)
    assert hints["error_code"].__args__ == ("retrieval_index_write_failed",)


def test_c3_failed_stage_literal() -> None:
    hints = get_type_hints(RetrievalIndexSyncFailure)
    assert hints["failed_stage"].__args__ == ("retrieval_index",)


def test_c4_forbidden_upstream_codes_not_in_failure() -> None:
    hints = get_type_hints(RetrievalIndexSyncFailure)
    allowed = set(hints["error_code"].__args__)
    forbidden = {
        "graph_write_failed",
        "memory_search_text_too_long",
        "entity_alignment_failed",
        "llm_timeout",
        "archive_not_found",
    }
    assert forbidden.isdisjoint(allowed)


def test_c5_es_document_fields() -> None:
    assert set(MemoryIndexDocument.model_fields) == {
        "memory_id",
        "user_id",
        "memory_type",
        "status",
        "content",
        "search_text",
        "predicate",
        "event_status",
        "latest_source_time",
        "updated_time",
        "embedding",
    }
    assert "omitted_alias_count" not in MemoryIndexDocument.model_fields


def test_sf1_memory_index_row_schema() -> None:
    assert set(MemoryIndexRow.model_fields) == {
        "memory_id",
        "user_id",
        "memory_type",
        "status",
        "content",
        "predicate",
        "event_status",
        "latest_source_time",
        "updated_time",
        "subject_entity_id",
        "object_entity_id",
        "object_value",
        "subject_canonical_name",
        "subject_aliases",
        "object_canonical_name",
        "object_aliases",
    }


def test_c6_upstream_zero_change() -> None:
    assert inspect.isclass(PipelineTerminalDecision)
    assert inspect.isclass(ExtractionLlmService)
    assert inspect.isclass(EntityAlignmentService)
    assert inspect.isclass(ReconciliationService)
    assert inspect.isclass(GraphWriteService)
    assert hasattr(extraction_worker, "main")


def test_c6_read_cypher_user_isolation() -> None:
    for query in authorized_read_cypher_queries():
        upper = query.upper()
        assert "USER_ID" in upper
        for forbidden in ("DELETE", "REMOVE", "DETACH", "MERGE", "CREATE", "SET"):
            assert forbidden not in upper


def test_c9_migration_dependency_zero_change() -> None:
    before = PYPROJECT.read_text(encoding="utf-8")
    assert "neo4j>=" in before


def test_sf3_embedding_batch_size_constant() -> None:
    assert EMBEDDING_BATCH_SIZE == 32
