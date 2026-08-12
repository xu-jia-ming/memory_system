"""Contract tests for the EXT-002 raw boundary and handoff envelope."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from memory_system.domain.models.extraction_preprocessing import (
    ExtractionReadyArchive,
    ValidatedRawArchive,
)
from memory_system.domain.services.extraction_archive_preprocessing_service import (
    validate_raw_archive,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_SOURCE = (
    REPO_ROOT
    / "src"
    / "memory_system"
    / "infrastructure"
    / "mongodb"
    / "context_archive_repository.py"
)


def _raw() -> dict[str, object]:
    return {
        "archive_id": "archive-1",
        "user_id": "user-1",
        "session_id": "session-1",
        "archive_batch_key": "batch-1",
        "base_compression_version": 0,
        "messages": [
            {
                "message_id": "message-1",
                "role": "user",
                "content": "content",
                "timestamp": 1_700_000_000,
            }
        ],
        "created_time": 1_700_000_000,
    }


def test_raw_archive_contract_has_exact_application_fields() -> None:
    archive = validate_raw_archive(_raw(), "archive-1")
    assert isinstance(archive, ValidatedRawArchive)
    assert set(archive.model_dump()) == {
        "archive_id",
        "user_id",
        "session_id",
        "archive_batch_key",
        "base_compression_version",
        "messages",
        "created_time",
    }


@pytest.mark.parametrize("value", [True, 1.0, "0", "2024-01-01T00:00:00Z"])
def test_integer_fields_reject_bool_coercion_and_datetime_like_values(value: object) -> None:
    document = _raw()
    document["base_compression_version"] = value
    with pytest.raises((TypeError, ValueError, ValidationError)):
        validate_raw_archive(document, "archive-1")


def test_storage_id_is_ignored_but_unknown_application_fields_are_rejected() -> None:
    document = _raw()
    document["_id"] = "mongo-only"
    assert "_id" not in validate_raw_archive(document, "archive-1").model_dump()
    document["unknown"] = "reject"
    with pytest.raises(ValueError):
        validate_raw_archive(document, "archive-1")


def test_ready_archive_contract_has_no_raw_or_temporary_fields() -> None:
    ready = ExtractionReadyArchive(
        archive_id="archive-1",
        user_id="user-1",
        session_id="session-1",
        messages=[],
    )
    assert set(ready.model_dump()) == {"archive_id", "user_id", "session_id", "messages"}
    assert "normalized_content" not in ready.model_dump()
    assert "raw_content" not in ready.model_dump()


def test_repository_keeps_typed_lookup_and_adds_only_raw_read() -> None:
    tree = ast.parse(REPOSITORY_SOURCE.read_text(encoding="utf-8"))
    functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
    }
    assert "find_context_archive_by_id" in functions
    assert "find_context_archive_document_by_id" in functions
    assert "insert_context_archive" in functions
