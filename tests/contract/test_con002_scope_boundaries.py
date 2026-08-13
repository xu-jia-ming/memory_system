"""CON-002 contract tests — scope boundaries (C1..C5)."""

from __future__ import annotations

import subprocess
from dataclasses import fields
from pathlib import Path

from memory_system.domain.models.consolidation_importance import ConsolidationImportanceInput
from memory_system.infrastructure.neo4j.consolidation_memory_read_repository import (
    Q_FETCH_CANDIDATE_BATCH,
    authorized_read_cypher_queries,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_COMMIT = "a3d0c26f1864e399d2562f1648c99584fe77d8e4"

ALLOWED_SRC_FILES = frozenset(
    {
        "src/memory_system/domain/models/consolidation_batch.py",
        "src/memory_system/domain/services/consolidation_batch_service.py",
        "src/memory_system/infrastructure/neo4j/consolidation_memory_read_repository.py",
    }
)

FORBIDDEN_MODIFIED_PREFIXES = (
    "src/memory_system/domain/services/act_r_scoring.py",
    "src/memory_system/domain/services/consolidation_importance.py",
    "src/memory_system/domain/models/consolidation_importance.py",
    "src/memory_system/domain/services/consolidation_worker.py",
    "src/memory_system/infrastructure/neo4j/retrieval_memory_read_repository.py",
    "src/memory_system/infrastructure/neo4j/retrieval_evidence_read_repository.py",
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
        queries = authorized_read_cypher_queries()
        assert len(queries) == 1
        query = queries[0]
        assert query == Q_FETCH_CANDIDATE_BATCH
        normalized = " ".join(query.split()).upper()
        required_fragments = [
            "MATCH (M:MEMORY)",
            "WHERE M.USER_ID = $USER_ID",
            "M.CREATED_TIME <= $EVALUATION_TIME",
            "M.LAST_CONSOLIDATED_TIME IS NULL OR M.LAST_CONSOLIDATED_TIME < $EVALUATION_TIME",
            "$CURSOR IS NULL OR M.MEMORY_ID > $CURSOR",
            "M.STATUS IN [\"ACTIVE\", \"CONFLICTED\", \"SUPERSEDED\"]",
            "OPTIONAL MATCH (E:EVIDENCE)-[:SUPPORTS]->(M)",
            "WHERE E.USER_ID = M.USER_ID",
            "COUNT(DISTINCT E.ARCHIVE_ID) AS INDEPENDENT_ARCHIVE_COUNT",
            "ORDER BY M.MEMORY_ID ASC",
            "LIMIT $BATCH_SIZE",
        ]
        for fragment in required_fragments:
            assert fragment in normalized, f"missing fragment: {fragment}"


class TestC3ForbiddenFilesUnmodified:
    def test_forbidden_paths_not_in_src_diff(self) -> None:
        changed = _git_diff_name_only(PLAN_COMMIT, "src/")
        for path in changed:
            for forbidden in FORBIDDEN_MODIFIED_PREFIXES:
                if forbidden.endswith("/"):
                    assert not path.startswith(forbidden), f"{path} modified under {forbidden}"
                else:
                    assert path != forbidden, f"{forbidden} was modified"

    def test_settings_directory_not_modified(self) -> None:
        changed = _git_diff_name_only(PLAN_COMMIT, "src/memory_system/settings/")
        assert changed == []


class TestC4HandoffInputFields:
    FORBIDDEN_FIELDS = frozenset(
        {"importance", "retrieval_count", "last_retrieved_time", "user_id"}
    )

    def test_input_has_no_forbidden_fields(self) -> None:
        field_names = {f.name for f in fields(ConsolidationImportanceInput)}
        overlap = self.FORBIDDEN_FIELDS & field_names
        assert overlap == set()

    def test_input_has_required_fields(self) -> None:
        field_names = {f.name for f in fields(ConsolidationImportanceInput)}
        required = {
            "memory_type",
            "confidence",
            "status",
            "created_time",
            "latest_source_time",
            "independent_archive_count",
            "evaluation_time",
        }
        assert required <= field_names


class TestC5DurableWriteScopeNone:
    def test_no_write_cypher_in_authorized_queries(self) -> None:
        for query in authorized_read_cypher_queries():
            upper = query.upper()
            assert "CREATE " not in upper
            assert "MERGE" not in upper
            assert "DELETE" not in upper
            assert "SET " not in upper

    def test_no_write_repository_module(self) -> None:
        write_repo = REPO_ROOT / (
            "src/memory_system/infrastructure/neo4j/"
            "consolidation_memory_write_repository.py"
        )
        assert not write_repo.exists()
