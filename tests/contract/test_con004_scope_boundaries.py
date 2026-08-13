"""CON-004 contract tests — scope boundaries (C1..C7)."""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

from memory_system.infrastructure.neo4j.consolidation_user_enumeration_repository import (
    Q_LIST_USER_IDS,
    authorized_enumeration_cypher_queries,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_COMMIT = "e124b23"

ALLOWED_SRC_FILES = frozenset(
    {
        "src/memory_system/domain/models/consolidation_run.py",
        "src/memory_system/domain/services/consolidation_run_service.py",
        "src/memory_system/infrastructure/consolidation_mutex.py",
        "src/memory_system/infrastructure/scheduling/consolidation_scheduler.py",
        "src/memory_system/infrastructure/neo4j/consolidation_user_enumeration_repository.py",
        "src/memory_system/observability/consolidation_run_telemetry.py",
        "src/memory_system/entrypoints/consolidation_worker.py",
    }
)

FORBIDDEN_MODIFIED_FILES = (
    "src/memory_system/domain/services/consolidation_importance.py",
    "src/memory_system/domain/models/consolidation_importance.py",
    "src/memory_system/domain/services/consolidation_batch_service.py",
    "src/memory_system/infrastructure/neo4j/consolidation_memory_read_repository.py",
    "src/memory_system/domain/models/consolidation_batch.py",
    "src/memory_system/domain/services/consolidation_write_service.py",
    "src/memory_system/infrastructure/neo4j/consolidation_memory_write_repository.py",
    "src/memory_system/domain/models/consolidation_write.py",
    "src/memory_system/settings/",
)


def _git_diff_name_only(rev: str, pathspec: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", rev, "--", pathspec],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


class TestC1ProductionWhitelist:
    def test_only_whitelisted_src_files_changed(self) -> None:
        changed = _git_diff_name_only(PLAN_COMMIT, "src/")
        unexpected = [path for path in changed if path not in ALLOWED_SRC_FILES]
        assert unexpected == [], f"unexpected src changes: {unexpected}"


class TestC2SchedulerNoInfiniteLoop:
    def test_job_callback_has_no_while_true(self) -> None:
        scheduler_path = (
            REPO_ROOT / "src/memory_system/infrastructure/scheduling/consolidation_scheduler.py"
        )
        tree = ast.parse(scheduler_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.While):
                if isinstance(node.test, ast.Constant) and node.test.value is True:
                    raise AssertionError("scheduler module contains while True loop")
        source = scheduler_path.read_text()
        assert "while True" not in source


class TestC3EnumerationCypherPredicates:
    def test_enumeration_cypher_contract(self) -> None:
        queries = authorized_enumeration_cypher_queries()
        assert len(queries) == 1
        query = queries[0]
        assert query == Q_LIST_USER_IDS
        normalized = " ".join(query.split()).upper()
        assert "RETURN DISTINCT M.USER_ID AS USER_ID" in normalized
        assert "ORDER BY M.USER_ID ASC" in normalized
        assert "M.CREATED_TIME <= $EVALUATION_TIME" in normalized
        assert "M.LAST_CONSOLIDATED_TIME IS NULL" in normalized


class TestC4Con001Con002Con003Unmodified:
    def test_forbidden_service_files_not_in_src_diff(self) -> None:
        changed = _git_diff_name_only(PLAN_COMMIT, "src/")
        for path in changed:
            for forbidden in FORBIDDEN_MODIFIED_FILES:
                if forbidden.endswith("/"):
                    assert not path.startswith(forbidden), f"{path} modified under {forbidden}"
                else:
                    assert path != forbidden, f"{forbidden} was modified"


class TestC5WorkerModifyAllowed:
    def test_consolidation_worker_is_whitelisted(self) -> None:
        assert "src/memory_system/entrypoints/consolidation_worker.py" in ALLOWED_SRC_FILES


class TestC6NoEsMongoKafkaInWorker:
    def test_worker_has_no_forbidden_clients(self) -> None:
        content = (REPO_ROOT / "src/memory_system/entrypoints/consolidation_worker.py").read_text()
        lowered = content.lower()
        assert "elasticsearch" not in lowered
        assert "mongo" not in lowered
        assert "kafka" not in lowered
        assert "aiokafka" not in lowered


class TestC7NoCon005IntegrationTests:
    def test_no_con005_test_files_in_diff(self) -> None:
        changed = _git_diff_name_only(PLAN_COMMIT, "tests/")
        con005 = [path for path in changed if "con005" in path.lower() or "integration" in path]
        assert con005 == []
