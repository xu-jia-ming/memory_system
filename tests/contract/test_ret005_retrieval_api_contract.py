"""Contract tests for RET-005 retrieval API."""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path

from memory_system.api.routes import memory_retrieval
from memory_system.api.schemas.memory_retrieval import RetrievalMemoryItem, RetrievalResponse
from memory_system.domain.services import retrieval_api_service
from memory_system.infrastructure.neo4j.retrieval_statistics_repository import (
    authorized_write_cypher_queries,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RETRIEVAL_PATH = "/api/v1/memory/retrieval"

AUTHORIZED_FATAL_CODES = frozenset(
    {
        "invalid_request",
        "invalid_memory_type",
        "invalid_top_k",
        "query_too_long",
        "retrieval_unavailable",
        "graph_load_failed",
        "retrieval_timeout",
        "internal_error",
        "invalid_api_key",
        "validation_error",
    }
)

FORBIDDEN_UPSTREAM = [
    "src/memory_system/domain/services/hybrid_retrieval_service.py",
    "src/memory_system/domain/services/rrf_fusion.py",
    "src/memory_system/domain/services/authoritative_recall_service.py",
    "src/memory_system/domain/services/retrieval_scoring_service.py",
]


def test_c1_route_path() -> None:
    routes = {route.path for route in memory_retrieval.router.routes}
    assert RETRIEVAL_PATH in routes


def test_c2_memory_api_key_dependency() -> None:
    for route in memory_retrieval.router.routes:
        dependency_names = [
            dep.call.__name__
            for dep in route.dependant.dependencies
            if dep.call is not None
        ]
        assert "require_memory_api_key" in dependency_names


def test_c3_authorized_http_fatal_codes_in_route() -> None:
    source = inspect.getsource(memory_retrieval) + inspect.getsource(retrieval_api_service)
    for code in (
        "invalid_request",
        "invalid_memory_type",
        "invalid_top_k",
        "query_too_long",
        "retrieval_unavailable",
        "graph_load_failed",
        "retrieval_timeout",
        "internal_error",
    ):
        assert code in source


def test_c4_stats_cypher_contains_user_id() -> None:
    for query in authorized_write_cypher_queries():
        assert "user_id: $user_id" in query


def test_c5_zero_upstream_production_diff() -> None:
    result = subprocess.run(
        ["git", "diff", "main", "--", *FORBIDDEN_UPSTREAM],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.stdout.strip() == ""


def test_c6_response_extra_forbid() -> None:
    assert RetrievalResponse.model_config.get("extra") == "forbid"
    assert RetrievalMemoryItem.model_config.get("extra") == "forbid"


def test_c7_score_field_not_final_score() -> None:
    fields = RetrievalMemoryItem.model_fields
    assert "score" in fields
    assert "final_score" not in fields


def test_authorized_fatal_codes_whitelist_subset() -> None:
    source = inspect.getsource(memory_retrieval) + inspect.getsource(retrieval_api_service)
    for code in AUTHORIZED_FATAL_CODES:
        if code in {"invalid_api_key", "validation_error"}:
            continue
        assert code in source or code in {"validation_error"}
