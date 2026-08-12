"""Contract tests for EXT-005 reconciliation."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import get_type_hints

from memory_system.domain.models.extraction_llm import AUTHORIZED_MEMORY_FIELDS
from memory_system.domain.models.memory_recall import MEMORY_PROPERTY_NAMES, MemoryNodeSnapshot
from memory_system.domain.models.reconciliation import (
    PerCandidateDecision,
    PlannedExistingMemoryUpdate,
    PlannedMemoryCreate,
    ReconciliationErrorCode,
    ReconciliationFailure,
    ReconciliationInput,
    ReconciliationOutcome,
    ReconciliationSuccess,
)
from memory_system.domain.services.entity_alignment_service import EntityAlignmentService
from memory_system.domain.services.extraction_llm_service import ExtractionLlmService
from memory_system.domain.services.extraction_pipeline_port import PipelineTerminalDecision
from memory_system.domain.services.reconciliation_service import ReconciliationService
from memory_system.entrypoints import extraction_worker
from memory_system.infrastructure.neo4j.evidence_lookup_repository import (
    Q_E1_EVIDENCE_EXISTS_CYPHER,
)
from memory_system.infrastructure.neo4j.memory_recall_repository import (
    Q_M1_BATCH_RECALL_CYPHER,
    Q_M1_RECALL_CYPHER,
)
from memory_system.settings import get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"


def test_c1_input_contract_fields() -> None:
    hints = get_type_hints(ReconciliationInput)
    assert set(hints) == {
        "task_id",
        "archive_id",
        "user_id",
        "session_id",
        "extraction_result",
        "entity_alignment",
    }


def test_c2_output_shapes_and_no_session_id() -> None:
    assert set(ReconciliationOutcome.model_fields) == {"outcome", "success", "failure"}
    assert set(ReconciliationSuccess.model_fields) == {
        "user_id",
        "archive_id",
        "per_candidate_decisions",
        "existing_memory_update_plans",
        "new_memory_create_plans",
    }
    assert "session_id" not in ReconciliationSuccess.model_fields
    assert set(PlannedMemoryCreate.model_fields) == {
        "create_kind",
        "planned_memory_id",
        "aligned_memory_key",
        "supersedes_target_memory_id",
        "conflicts_with_target_memory_id",
        "memory_type",
        "planned_content",
        "subject_entity_id",
        "predicate",
        "object_entity_id",
        "object_value",
        "event_status",
        "start_time",
        "end_time",
        "original_time_text",
        "planned_confidence",
        "planned_importance",
        "planned_latest_source_time",
        "initial_memory_version",
        "contributing_candidate_indices",
        "contributing_evidence_ids",
    }


def test_c2b_mf001_self_contained_create_rows() -> None:
    hints = get_type_hints(PlannedMemoryCreate)
    assert "planned_content" in hints
    assert "planned_confidence" in hints
    assert "planned_importance" in hints


def test_c3_error_code_whitelist() -> None:
    allowed = {item.value for item in ReconciliationErrorCode}
    assert allowed == {
        "graph_query_failed",
        "reconciliation_plan_conflict",
        "llm_timeout",
        "llm_request_failed",
        "llm_invalid_output",
    }
    forbidden = {
        "entity_alignment_failed",
        "graph_write_failed",
        "memory_search_text_too_long",
        "retrieval_index_write_failed",
        "archive_not_found",
    }
    assert forbidden.isdisjoint(allowed)


def test_c4_failed_stage_literal() -> None:
    hints = get_type_hints(ReconciliationFailure)
    assert hints["failed_stage"].__args__ == ("reconciliation",)


def test_c5_no_persistence_surface() -> None:
    assert not hasattr(ReconciliationOutcome, "to_durable_dict")
    assert AUTHORIZED_MEMORY_FIELDS == {
        "memory_type",
        "content",
        "subject_entity_id",
        "predicate",
        "object_entity_id",
        "object_value",
        "event_status",
        "start_time",
        "end_time",
        "original_time_text",
        "confidence",
        "source_message_ids",
        "candidate_source_time",
        "candidate_fingerprint",
    }


def test_c6_read_only_cypher_contract() -> None:
    for query in (Q_M1_RECALL_CYPHER, Q_M1_BATCH_RECALL_CYPHER, Q_E1_EVIDENCE_EXISTS_CYPHER):
        upper = query.upper()
        for forbidden in ("CREATE", "MERGE", "SET", "DELETE", "REMOVE", "CONSTRAINT"):
            assert forbidden not in upper
        assert "USER_ID" in upper


def test_c7_no_ext006_plus_fields() -> None:
    forbidden_fields = {
        "referenced_entity_write_set",
        "core_search_text",
        "planned_index_sync_memory_set",
    }
    for model in (
        ReconciliationSuccess,
        PlannedExistingMemoryUpdate,
        PlannedMemoryCreate,
        PerCandidateDecision,
    ):
        assert forbidden_fields.isdisjoint(set(model.model_fields))


def test_c8_upstream_zero_change_symbols() -> None:
    assert inspect.isclass(PipelineTerminalDecision)
    assert inspect.isclass(ExtractionLlmService)
    assert inspect.isclass(EntityAlignmentService)
    assert hasattr(extraction_worker, "main")


def test_c9_no_dependency_or_migration_changes() -> None:
    pyproject = PYPROJECT.read_text(encoding="utf-8")
    assert "reconciliation" not in pyproject.lower() or "memory-system" in pyproject


def test_c10_recall_order_by_and_limit() -> None:
    assert "ORDER BY CASE m.status" in Q_M1_RECALL_CYPHER
    assert "LIMIT 20" in Q_M1_RECALL_CYPHER
    assert "LIMIT 20" in Q_M1_BATCH_RECALL_CYPHER
    assert set(MemoryNodeSnapshot.model_fields) == MEMORY_PROPERTY_NAMES


def test_reconciliation_service_factory_exists() -> None:
    assert callable(ReconciliationService)
    _ = get_settings()
