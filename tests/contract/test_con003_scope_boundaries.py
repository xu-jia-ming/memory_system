"""CON-003 contract tests — scope boundaries (C1..C6)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from memory_system.infrastructure.neo4j.consolidation_memory_write_repository import (
    Q_WRITE_IMPORTANCE_BATCH,
    authorized_write_cypher_queries,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_COMMIT = "0146b5dd53d37dfbdec0ea9bc9e87d6fe373221a"

ALLOWED_SRC_FILES = frozenset(
    {
        "src/memory_system/domain/models/consolidation_write.py",
        "src/memory_system/domain/services/consolidation_write_service.py",
        "src/memory_system/infrastructure/neo4j/consolidation_memory_write_repository.py",
    }
)

FORBIDDEN_MODIFIED_PREFIXES = (
    "src/memory_system/domain/services/consolidation_importance.py",
    "src/memory_system/domain/models/consolidation_importance.py",
    "src/memory_system/domain/services/consolidation_batch_service.py",
    "src/memory_system/infrastructure/neo4j/consolidation_memory_read_repository.py",
    "src/memory_system/domain/models/consolidation_batch.py",
    "src/memory_system/entrypoints/consolidation_worker.py",
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
        unexpected = [p for p in changed if p not in ALLOWED_SRC_FILES]
        assert unexpected == [], f"unexpected src changes: {unexpected}"


class TestC2AuthorizedCypherFullPredicates:
    def test_full_cypher_predicates(self) -> None:
        queries = authorized_write_cypher_queries()
        assert len(queries) == 1
        query = queries[0]
        assert query == Q_WRITE_IMPORTANCE_BATCH
        normalized = " ".join(query.split()).upper()
        required_fragments = [
            "UNWIND $ROWS AS ROW",
            "MATCH (M:MEMORY {MEMORY_ID: ROW.MEMORY_ID})",
            "WHERE M.USER_ID = ROW.USER_ID",
            "AND M.MEMORY_VERSION = ROW.EXPECTED_MEMORY_VERSION",
            "SET M.IMPORTANCE = ROW.IMPORTANCE",
            "M.LAST_CONSOLIDATED_TIME = $EVALUATION_TIME",
            "RETURN COUNT(M) AS UPDATED_COUNT",
        ]
        for fragment in required_fragments:
            assert fragment in normalized, f"missing fragment: {fragment}"


class TestC3NoMemoryVersionOrUpdatedTimeSet:
    def test_cypher_has_no_forbidden_sets(self) -> None:
        upper = Q_WRITE_IMPORTANCE_BATCH.upper()
        assert "SET M.MEMORY_VERSION" not in upper
        assert "SET M.UPDATED_TIME" not in upper
        stripped = upper.replace("LAST_CONSOLIDATED_TIME", "")
        assert "UPDATED_TIME" not in stripped


class TestC4Con001Con002ReadPathsUnmodified:
    def test_forbidden_read_paths_not_in_src_diff(self) -> None:
        changed = _git_diff_name_only(PLAN_COMMIT, "src/")
        for path in changed:
            for forbidden in FORBIDDEN_MODIFIED_PREFIXES:
                if forbidden.endswith("/"):
                    assert not path.startswith(forbidden), f"{path} modified under {forbidden}"
                else:
                    assert path != forbidden, f"{forbidden} was modified"


class TestC5DurableWriteScopeNeo4jOnly:
    def test_write_repository_exists(self) -> None:
        write_repo = REPO_ROOT / (
            "src/memory_system/infrastructure/neo4j/"
            "consolidation_memory_write_repository.py"
        )
        assert write_repo.exists()

    def test_no_es_mongo_kafka_in_write_module(self) -> None:
        content = (
            REPO_ROOT
            / "src/memory_system/infrastructure/neo4j/"
            "consolidation_memory_write_repository.py"
        ).read_text()
        lowered = content.lower()
        assert "elasticsearch" not in lowered
        assert "mongo" not in lowered
        assert "kafka" not in lowered


class TestC6WorkerAndSettingsUnmodified:
    def test_settings_directory_not_modified(self) -> None:
        changed = _git_diff_name_only(PLAN_COMMIT, "src/memory_system/settings/")
        assert changed == []

    def test_consolidation_worker_not_modified(self) -> None:
        changed = _git_diff_name_only(PLAN_COMMIT, "src/")
        assert "src/memory_system/entrypoints/consolidation_worker.py" not in changed
