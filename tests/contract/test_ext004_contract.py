"""Contract tests for EXT-004 entity alignment."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import get_type_hints

from memory_system.domain.enums.extraction_task import PipelineTerminalKind
from memory_system.domain.models.entity_alignment import (
    ENTITY_PROPERTY_NAMES,
    AlignedEntity,
    EntityAlignmentFailure,
    EntityAlignmentInput,
    EntityAlignmentOutcome,
    EntityNodeSnapshot,
    PlannedEntityAliasMerge,
)
from memory_system.domain.models.extraction_llm import (
    AUTHORIZED_ENTITY_FIELDS,
    AUTHORIZED_MEMORY_FIELDS,
    ENTITY_TYPES,
    ExtractionEntityCandidate,
)
from memory_system.domain.services.entity_alignment_service import EntityAlignmentService
from memory_system.domain.services.entity_key import (
    compute_entity_key,
    normalize_entity_name,
    planned_user_entity_fields,
)
from memory_system.domain.services.extraction_llm_service import ExtractionLlmService
from memory_system.domain.services.extraction_pipeline_port import PipelineTerminalDecision
from memory_system.entrypoints import extraction_worker
from memory_system.infrastructure.neo4j.entity_alignment_repository import (
    Q1_USER_ENTITY_CYPHER,
    Q2_ENTITY_KEY_BATCH_CYPHER,
    Q3_SECONDARY_MATCH_CYPHER,
)
from memory_system.settings import get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
NEO4J_MIGRATION = REPO_ROOT / "scripts" / "migrations" / "002_initial_neo4j.py"


def test_c1_input_contract_fields() -> None:
    hints = get_type_hints(EntityAlignmentInput)
    assert set(hints) == {
        "task_id",
        "archive_id",
        "user_id",
        "entities",
        "referenced_local_entity_ids",
    }
  # entities use ExtractionEntityCandidate only
    assert set(ExtractionEntityCandidate.model_fields) == AUTHORIZED_ENTITY_FIELDS


def test_c2_output_contract_shapes() -> None:
    assert set(EntityAlignmentOutcome.model_fields) == {"outcome", "success", "failure"}
    assert set(AlignedEntity.model_fields) == {
        "local_entity_id",
        "entity_id",
        "match_kind",
        "entity_type",
        "canonical_name",
        "normalized_name",
        "entity_key",
        "planned_alias_merge",
        "existing_entity",
        "planned_create",
    }
    assert set(PlannedEntityAliasMerge.model_fields) == {
        "normalized_candidate_aliases",
        "existing_aliases",
        "planned_aliases",
        "omitted_alias_count",
        "canonical_name_replaced",
    }
    assert set(EntityNodeSnapshot.model_fields) == ENTITY_PROPERTY_NAMES


def test_c3_entity_property_names() -> None:
    assert ENTITY_PROPERTY_NAMES == {
        "entity_id",
        "user_id",
        "entity_key",
        "entity_type",
        "canonical_name",
        "normalized_name",
        "aliases",
    }


def test_c4_entity_key_formula_vector() -> None:
    user_id = "u1"
    entity_type = "person"
    normalized_name = "alice"
    assert compute_entity_key(
        user_id=user_id,
        entity_type=entity_type,
        normalized_name=normalized_name,
    ) == compute_entity_key(
        user_id=user_id,
        entity_type=entity_type,
        normalized_name=normalize_entity_name("Alice"),
    )


def test_c5_user_entity_fixed_fields() -> None:
    fields = planned_user_entity_fields("user-9")
    assert fields["entity_id"] == "user:user-9"
    assert fields["entity_type"] == "person"
    assert fields["canonical_name"] == "current_user"
    assert fields["normalized_name"] == "current_user"
    assert fields["aliases"] == []


def test_c6_entity_type_enum_unchanged() -> None:
    assert ENTITY_TYPES == {
        "person",
        "organization",
        "product",
        "project",
        "location",
        "concept",
        "other",
    }


def test_c7_error_code_whitelist() -> None:
    hints = get_type_hints(EntityAlignmentFailure)
    assert hints["error_code"].__args__ == ("entity_alignment_failed",)


def test_c8_failed_stage_literal() -> None:
    hints = get_type_hints(EntityAlignmentFailure)
    assert hints["failed_stage"].__args__ == ("entity_alignment",)


def test_c9_no_persistence_surface() -> None:
    assert not hasattr(EntityAlignmentOutcome, "to_durable_dict")
    assert AUTHORIZED_ENTITY_FIELDS == {"local_entity_id", "name", "type", "aliases"}
    assert "candidate_fingerprint" in AUTHORIZED_MEMORY_FIELDS


def test_c10_read_only_cypher_contract() -> None:
    for query in (Q1_USER_ENTITY_CYPHER, Q2_ENTITY_KEY_BATCH_CYPHER, Q3_SECONDARY_MATCH_CYPHER):
        upper = query.upper()
        for forbidden in ("CREATE", "MERGE", "SET", "DELETE", "REMOVE", "CONSTRAINT", "INDEX"):
            assert forbidden not in upper
        assert "user_id" in query


def test_c11_no_ext005_fields_on_output_models() -> None:
    forbidden = {
        "aligned_memory_key",
        "memory_id",
        "evidence_id",
        "action",
        "reason_code",
        "merged_content",
        "increment_memory_version",
        "referenced_entity_write_set",
        "core_search_text",
        "importance",
        "confidence",
        "memory_version",
    }
    output_models = (
        EntityAlignmentOutcome,
        AlignedEntity,
        PlannedEntityAliasMerge,
        EntityNodeSnapshot,
    )
    for model in output_models:
        assert forbidden.isdisjoint(model.model_fields)


def test_c12_upstream_unchanged() -> None:
    assert {item.value for item in PipelineTerminalKind} == {
        "complete",
        "fail",
        "abort_without_terminal",
    }
    factories = {"complete", "fail", "abort_without_terminal"}
    assert factories.issubset(dir(PipelineTerminalDecision))
    assert inspect.isfunction(extraction_worker.main)
    assert "abort_without_terminal" in inspect.getsource(ExtractionLlmService.run)


def test_c13_migration_unchanged() -> None:
    content = NEO4J_MIGRATION.read_text(encoding="utf-8")
    for name in (
        "entity_id_unique",
        "entity_key_unique",
        "memory_id_unique",
        "evidence_id_unique",
        "memory_user_type_status",
        "memory_subject_predicate",
    ):
        assert name in content


def test_c14_dependency_neo4j_present() -> None:
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"neo4j>=5.28,<6"' in pyproject


def test_c15_alias_limit_from_settings() -> None:
    settings = get_settings()
    service = EntityAlignmentService(
        repository=object(),  # type: ignore[arg-type]
        max_stored_entity_alias_count=settings.memory_extraction.max_stored_entity_alias_count,
    )
    assert service._max_stored_entity_alias_count == 50  # noqa: SLF001


def test_c7_forbidden_error_codes_negative() -> None:
    sample = EntityAlignmentFailure().model_dump()
    forbidden = (
        "graph_query_failed",
        "reconciliation_plan_conflict",
        "graph_write_failed",
        "memory_search_text_too_long",
        "retrieval_index_write_failed",
    )
    for token in forbidden:
        assert token not in str(sample)
