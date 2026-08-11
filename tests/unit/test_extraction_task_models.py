"""Unit tests for MemoryExtractionTask models and enums (EXT-001)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.domain.models.extraction_task import ExtractionLastError, MemoryExtractionTask

C1_FIELDS = {
    "task_id",
    "archive_id",
    "user_id",
    "status",
    "attempt_count",
    "extraction_result",
    "last_error",
    "created_time",
    "updated_time",
    "completed_time",
}


def _minimal_task(**overrides: object) -> MemoryExtractionTask:
    payload: dict[str, object] = {
        "task_id": "11111111-1111-4111-8111-111111111111",
        "archive_id": "arch-1",
        "user_id": "user-1",
        "status": ExtractionTaskStatus.PENDING,
        "attempt_count": 0,
        "extraction_result": None,
        "last_error": None,
        "created_time": 1_700_000_000,
        "updated_time": 1_700_000_000,
        "completed_time": None,
    }
    payload.update(overrides)
    return MemoryExtractionTask.model_validate(payload)


def test_task_model_c1_fields_only() -> None:
    task = _minimal_task()
    assert set(task.model_dump().keys()) == C1_FIELDS
    assert "session_id" not in task.model_dump()
    assert "event_id" not in task.model_dump()


def test_task_model_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        MemoryExtractionTask.model_validate(
            {
                "task_id": "11111111-1111-4111-8111-111111111111",
                "archive_id": "a1",
                "user_id": "u1",
                "status": "pending",
                "attempt_count": 0,
                "extraction_result": None,
                "last_error": None,
                "created_time": 1,
                "updated_time": 1,
                "completed_time": None,
                "session_id": "must-reject",
            }
        )


@pytest.mark.parametrize(
    "task_id",
    [
        "not-a-uuid",
        "t1",
        "6ba7b810-9dad-11d1-80b4-00c04fd430c8",  # UUID v1
    ],
)
def test_task_id_must_be_uuid_v4(task_id: str) -> None:
    with pytest.raises(ValidationError):
        _minimal_task(task_id=task_id)


def test_task_id_accepts_uuid_v4() -> None:
    task = _minimal_task(task_id="550e8400-e29b-41d4-a716-446655440000")
    assert task.task_id == "550e8400-e29b-41d4-a716-446655440000"


def test_status_enum_four_values() -> None:
    assert {s.value for s in ExtractionTaskStatus} == {
        "pending",
        "processing",
        "completed",
        "failed",
    }


def test_last_error_three_field_shape() -> None:
    err = ExtractionLastError(
        error_code="graph_write_failed",
        failed_stage="graph_write",
        message="neo4j unavailable",
    )
    dumped = err.model_dump(mode="json")
    assert dumped == {
        "error_code": "graph_write_failed",
        "failed_stage": "graph_write",
        "message": "neo4j unavailable",
    }
    task = _minimal_task(status=ExtractionTaskStatus.FAILED, last_error=err, attempt_count=1)
    assert task.last_error is not None
    assert task.last_error.error_code == "graph_write_failed"


def test_last_error_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        ExtractionLastError.model_validate(
            {
                "error_code": "x",
                "failed_stage": "y",
                "message": "z",
                "extra": True,
            }
        )


def test_illegal_status_rejected() -> None:
    with pytest.raises(ValidationError):
        _minimal_task(status="retrying")
