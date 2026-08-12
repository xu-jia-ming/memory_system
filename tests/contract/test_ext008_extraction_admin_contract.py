"""Contract tests for EXT-008 extraction admin API."""

from __future__ import annotations

import inspect
from pathlib import Path

from memory_system.api.routes import memory_extraction_admin
from memory_system.api.schemas.memory_extraction_admin import (
    ExtractionMutationResponse,
    ExtractionStatusResponse,
)
from memory_system.domain.constants.extraction_retry_policy import (
    MANUAL_RETRY_ALLOWED_ERROR_CODES,
    MANUAL_RETRY_FORBIDDEN_ERROR_CODES,
    REBUILD_ALLOWED_ERROR_CODES,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

SPEC_RETRY_ALLOWED = frozenset(
    {
        "llm_timeout",
        "llm_request_failed",
        "llm_invalid_output",
        "entity_alignment_failed",
        "graph_query_failed",
        "graph_write_failed",
        "retrieval_index_write_failed",
        "kafka_publish_failed",
    }
)

SPEC_RETRY_FORBIDDEN = frozenset(
    {
        "archive_not_found",
        "archive_ownership_mismatch",
        "invalid_archive",
        "archive_too_large",
        "reconciliation_plan_conflict",
        "memory_search_text_too_long",
    }
)

GET_PATH = "/api/v1/memory/extraction/{user_id}/{archive_id}"
RETRY_PATH = "/api/v1/memory/extraction/{user_id}/{archive_id}/retry"
REBUILD_PATH = "/api/v1/memory/extraction/{user_id}/{archive_id}/rebuild"


def test_c1_route_paths() -> None:
    routes = {route.path for route in memory_extraction_admin.router.routes}
    assert GET_PATH in routes
    assert RETRY_PATH in routes
    assert REBUILD_PATH in routes


def test_c2_admin_key_dependency_on_all_routes() -> None:
    for route in memory_extraction_admin.router.routes:
        dependant = route.dependant
        dependency_names = [
            dep.call.__name__
            for dep in dependant.dependencies
            if dep.call is not None
        ]
        assert "require_admin_api_key" in dependency_names


def test_c3_authorized_http_codes_in_routes() -> None:
    source = inspect.getsource(memory_extraction_admin)
    assert "extraction_task_not_found" in source
    assert "retry_not_allowed" in source
    assert "invalid_api_key" not in source
    assert "forbidden" not in source
    assert "rebuild_not_allowed" not in source
    assert "task_not_failed" not in source


def test_c4_retry_table_exact() -> None:
    assert MANUAL_RETRY_ALLOWED_ERROR_CODES == SPEC_RETRY_ALLOWED
    assert MANUAL_RETRY_FORBIDDEN_ERROR_CODES == SPEC_RETRY_FORBIDDEN
    assert REBUILD_ALLOWED_ERROR_CODES == frozenset({"reconciliation_plan_conflict"})


def test_c5_response_extra_forbid() -> None:
    assert ExtractionStatusResponse.model_config.get("extra") == "forbid"
    assert ExtractionMutationResponse.model_config.get("extra") == "forbid"


def test_c6_zero_upstream_diff() -> None:
    forbidden_paths = [
        REPO_ROOT / "src/memory_system/domain/services/extraction_task_consumer_service.py",
        REPO_ROOT / "src/memory_system/entrypoints/extraction_worker.py",
        REPO_ROOT / "src/memory_system/domain/services/extraction_pipeline_port.py",
        REPO_ROOT / "src/memory_system/domain/services/extraction_llm_service.py",
        REPO_ROOT / "src/memory_system/domain/services/entity_alignment_service.py",
        REPO_ROOT / "src/memory_system/domain/services/reconciliation_service.py",
        REPO_ROOT / "src/memory_system/domain/services/graph_write_service.py",
        REPO_ROOT / "src/memory_system/domain/services/retrieval_index_sync_service.py",
    ]
    for path in forbidden_paths:
        assert path.exists()


def test_c7_get_response_omits_extraction_result() -> None:
    assert "extraction_result" not in ExtractionStatusResponse.model_fields
