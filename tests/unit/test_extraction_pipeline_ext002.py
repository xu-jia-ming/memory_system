"""EXT-002 pipeline decisions through the existing EXT-001 terminal gate."""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import AsyncMock, Mock, patch

import pytest

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus, PipelineTerminalKind
from memory_system.domain.models.archive_created_event import ArchiveCreatedEvent
from memory_system.domain.models.extraction_task import ExtractionLastError, MemoryExtractionTask
from memory_system.domain.services.extraction_archive_preprocessing_service import (
    ExtractionArchivePreprocessingService,
)
from memory_system.domain.services.extraction_pipeline_port import PipelineTerminalDecision
from memory_system.domain.services.extraction_redaction_service import RedactionFailure
from memory_system.domain.services.extraction_task_consumer_service import (
    TerminalPersistError,
    process_archive_created_event,
)

NOW = 1_700_000_000


def _event() -> ArchiveCreatedEvent:
    return ArchiveCreatedEvent(
        event_id="event-1",
        archive_id="archive-1",
        user_id="user-1",
        session_id="session-1",
        created_time=NOW,
    )


def _task() -> MemoryExtractionTask:
    return MemoryExtractionTask(
        task_id="11111111-1111-4111-8111-111111111111",
        archive_id="archive-1",
        user_id="user-1",
        status=ExtractionTaskStatus.PROCESSING,
        attempt_count=1,
        created_time=NOW,
        updated_time=NOW,
    )


def _archive() -> dict[str, object]:
    return {
        "archive_id": "archive-1",
        "user_id": "user-1",
        "session_id": "session-1",
        "archive_batch_key": "batch-1",
        "base_compression_version": 0,
        "messages": [],
        "created_time": NOW,
    }


@pytest.mark.asyncio
async def test_missing_archive_is_failed_without_pipeline_side_effects() -> None:
    repository = AsyncMock()
    repository.find_context_archive_document_by_id.return_value = None
    service = ExtractionArchivePreprocessingService(AsyncMock(), repository=repository)

    decision = await service.run(_task(), _event())

    assert decision.kind == PipelineTerminalKind.FAIL
    assert decision.last_error == ExtractionLastError(
        error_code="archive_not_found",
        failed_stage="archive_read",
        message="archive was not found",
    )
    assert service.last_ready_archive is None


@pytest.mark.asyncio
async def test_RED_18_redaction_failure_has_no_handoff() -> None:
    repository = AsyncMock()
    repository.find_context_archive_document_by_id.return_value = _archive() | {
        "messages": [
            {
                "message_id": "message-1",
                "role": "user",
                "content": "password: secret",
                "timestamp": NOW,
            }
        ]
    }
    redactor = Mock()
    redactor.redact.side_effect = RedactionFailure("detector failed")
    service = ExtractionArchivePreprocessingService(
        AsyncMock(), repository=repository, redactor=redactor
    )

    decision, ready = await service.prepare(_task(), _event())

    assert decision.last_error is not None
    assert decision.last_error.error_code == "redaction_failed"
    assert decision.last_error.failed_stage == "redaction"
    assert ready is None


@pytest.mark.asyncio
async def test_unexpected_redactor_exception_aborts_without_terminal() -> None:
    repository = AsyncMock()
    repository.find_context_archive_document_by_id.return_value = _archive() | {
        "messages": [
            {
                "message_id": "message-1",
                "role": "user",
                "content": "ordinary content",
                "timestamp": NOW,
            }
        ]
    }
    redactor = Mock()
    redactor.redact.side_effect = RuntimeError("internal detector bug")
    service = ExtractionArchivePreprocessingService(
        AsyncMock(), repository=repository, redactor=redactor
    )

    decision, ready = await service.prepare(_task(), _event())

    assert decision.kind == PipelineTerminalKind.ABORT_WITHOUT_TERMINAL
    assert decision.last_error is None
    assert ready is None


@pytest.mark.asyncio
async def test_token_estimator_exception_aborts_without_terminal() -> None:
    repository = AsyncMock()
    repository.find_context_archive_document_by_id.return_value = _archive() | {
        "messages": [
            {
                "message_id": "message-1",
                "role": "user",
                "content": "ordinary content",
                "timestamp": NOW,
            }
        ]
    }
    service = ExtractionArchivePreprocessingService(AsyncMock(), repository=repository)
    with patch(
        "memory_system.domain.services.extraction_archive_preprocessing_service.estimate_tokens",
        side_effect=RuntimeError("estimator unavailable"),
    ):
        decision, ready = await service.prepare(_task(), _event())

    assert decision.kind == PipelineTerminalKind.ABORT_WITHOUT_TERMINAL
    assert decision.last_error is None
    assert ready is None


@pytest.mark.asyncio
async def test_normalization_exception_aborts_without_terminal() -> None:
    repository = AsyncMock()
    repository.find_context_archive_document_by_id.return_value = _archive() | {
        "messages": [
            {
                "message_id": "message-1",
                "role": "user",
                "content": "ordinary content",
                "timestamp": NOW,
            }
        ]
    }
    service = ExtractionArchivePreprocessingService(AsyncMock(), repository=repository)
    with patch(
        "memory_system.domain.services.extraction_archive_preprocessing_service.normalize_content",
        side_effect=RuntimeError("normalizer unavailable"),
    ):
        decision, ready = await service.prepare(_task(), _event())

    assert decision.kind == PipelineTerminalKind.ABORT_WITHOUT_TERMINAL
    assert decision.last_error is None
    assert ready is None


@pytest.mark.asyncio
async def test_RED_19_terminal_persistence_failure_prevents_offset_commit() -> None:
    error = ExtractionLastError(
        error_code="archive_not_found",
        failed_stage="archive_read",
        message="archive was not found",
    )
    pipeline = AsyncMock()
    pipeline.run.return_value = PipelineTerminalDecision.fail(error)
    processing = _task()
    with (
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo"
            ".upsert_pending_extraction_task",
            new_callable=AsyncMock,
            return_value=processing,
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo"
            ".bump_processing_attempt",
            new_callable=AsyncMock,
            return_value=processing,
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo"
            ".mark_failed",
            new_callable=AsyncMock,
            side_effect=RuntimeError("mongo unavailable"),
        ),
    ):
        with pytest.raises(TerminalPersistError):
            await process_archive_created_event(
                mongodb=AsyncMock(),
                event=_event(),
                pipeline=pipeline,
                clock=lambda: NOW,
            )


@pytest.mark.asyncio
async def test_RED_20_abort_decision_does_not_persist_or_commit_offset() -> None:
    pipeline = AsyncMock()
    pipeline.run.return_value = PipelineTerminalDecision.abort_without_terminal()
    processing = _task()
    with (
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo"
            ".upsert_pending_extraction_task",
            new_callable=AsyncMock,
            return_value=processing,
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo"
            ".bump_processing_attempt",
            new_callable=AsyncMock,
            return_value=processing,
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo.mark_failed",
            new_callable=AsyncMock,
        ) as mark_failed,
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo.mark_completed",
            new_callable=AsyncMock,
        ) as mark_completed,
    ):
        result = await process_archive_created_event(
            mongodb=AsyncMock(),
            event=_event(),
            pipeline=pipeline,
            clock=lambda: NOW,
        )

    assert result.should_commit_offset is False
    mark_failed.assert_not_awaited()
    mark_completed.assert_not_awaited()


@pytest.mark.asyncio
async def test_RAW_01_valid_archive_crosses_the_real_pipeline_boundary() -> None:
    repository = AsyncMock()
    repository.find_context_archive_document_by_id.return_value = _archive() | {
        "messages": [
            {
                "message_id": "message-1",
                "role": "user",
                "content": "ordinary content",
                "timestamp": NOW,
            }
        ]
    }
    service = ExtractionArchivePreprocessingService(AsyncMock(), repository=repository)

    decision = await service.run(_task(), _event())

    assert decision.kind == PipelineTerminalKind.COMPLETE
    assert service.last_ready_archive is not None
    assert service.last_ready_archive.messages[0].content == "ordinary content"


def _raw_invalid_cases() -> list[tuple[str, dict[str, object]]]:
    cases: list[tuple[str, dict[str, object]]] = []
    for field in (
        "archive_id",
        "user_id",
        "session_id",
        "archive_batch_key",
        "base_compression_version",
        "messages",
        "created_time",
    ):
        missing = _archive()
        del missing[field]
        cases.append((f"RAW-02-{field}-missing", missing))
        null = _archive()
        null[field] = None
        cases.append((f"RAW-02-{field}-null", null))
    for field, value in (
        ("archive_id", 1),
        ("user_id", {}),
        ("session_id", []),
        ("archive_batch_key", 1.0),
        ("base_compression_version", "0"),
        ("messages", {}),
        ("created_time", "now"),
    ):
        invalid = _archive()
        invalid[field] = value
        cases.append((f"RAW-04-{field}", invalid))
    for field in ("archive_id", "user_id", "session_id", "archive_batch_key"):
        invalid = _archive()
        invalid[field] = ""
        cases.append((f"RAW-03-{field}", invalid))
    empty_message_id = _archive() | {
        "messages": [
            {
                "message_id": "message-1",
                "role": "user",
                "content": "secret",
                "timestamp": NOW,
            }
        ]
    }
    empty_message_id["messages"][0]["message_id"] = ""
    cases.append(("RAW-03-message_id", empty_message_id))
    for field in ("base_compression_version", "created_time"):
        for value in (True, 1.5, "1", "2024-01-01T00:00:00Z"):
            invalid = _archive()
            invalid[field] = value
            cases.append((f"RAW-05-{field}-{type(value).__name__}", invalid))
    for messages in (None, {}, "message", [None], [1], [{}]):
        invalid = _archive()
        invalid["messages"] = messages
        cases.append((f"RAW-06-{type(messages).__name__}", invalid))
    for field in ("message_id", "role", "content", "timestamp"):
        invalid = _archive() | {
            "messages": [
                {
                    "message_id": "message-1",
                    "role": "user",
                    "content": "secret",
                    "timestamp": NOW,
                }
            ]
        }
        del invalid["messages"][0][field]
        cases.append((f"RAW-07-{field}-missing", invalid))
        null = deepcopy(invalid)
        null["messages"][0][field] = None
        cases.append((f"RAW-07-{field}-null", null))
    for field, value in (
        ("message_id", 1),
        ("role", {}),
        ("content", b"secret"),
        ("timestamp", 1.5),
    ):
        invalid = _archive() | {
            "messages": [
                {
                    "message_id": "message-1",
                    "role": "user",
                    "content": "secret",
                    "timestamp": NOW,
                }
            ]
        }
        invalid["messages"][0][field] = value
        cases.append((f"RAW-07-{field}-wrong-type", invalid))
    for role in ("USER", "system", 1, {}):
        invalid = _archive() | {
            "messages": [
                {
                    "message_id": "message-1",
                    "role": role,
                    "content": "secret",
                    "timestamp": NOW,
                }
            ]
        }
        cases.append((f"RAW-08-{role!s}", invalid))
    top_unknown = _archive()
    top_unknown["unknown"] = True
    cases.append(("RAW-09-top-level", top_unknown))
    message_unknown = _archive() | {
        "messages": [
            {
                "message_id": "message-1",
                "role": "user",
                "content": "secret",
                "timestamp": NOW,
                "unknown": True,
            }
        ]
    }
    cases.append(("RAW-09-message", message_unknown))
    invalid_later = _archive() | {
        "messages": [
            {
                "message_id": "message-1",
                "role": "user",
                "content": "secret",
                "timestamp": NOW,
            },
            {
                "message_id": "message-2",
                "role": "assistant",
                "content": 7,
                "timestamp": NOW,
            },
        ]
    }
    cases.append(("RAW-12-no-partial-output", invalid_later))
    return cases


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case_id", "document"),
    _raw_invalid_cases(),
    ids=lambda value: value if isinstance(value, str) else None,
)
async def test_RAW_invalid_cases_fail_at_the_real_pipeline_boundary(
    case_id: str, document: dict[str, object]
) -> None:
    repository = AsyncMock()
    repository.find_context_archive_document_by_id.return_value = deepcopy(document)
    redactor = Mock()
    service = ExtractionArchivePreprocessingService(
        AsyncMock(), repository=repository, redactor=redactor
    )

    decision = await service.run(_task(), _event())

    assert case_id.startswith("RAW-")
    assert decision.kind == PipelineTerminalKind.FAIL
    assert decision.last_error is not None
    assert decision.last_error.error_code == "invalid_archive"
    assert decision.last_error.failed_stage == "archive_validate"
    assert service.last_ready_archive is None
    redactor.redact.assert_not_called()


@pytest.mark.asyncio
async def test_RED_16_17_21_22_23_27_real_pipeline_handoff_is_safe_and_repeatable(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "sk-abcdefghijklmnopqrstuvwxyz"
    raw = _archive() | {
        "messages": [
            {
                "message_id": "message-1",
                "role": "user",
                "content": f"I am Alice; api-key={secret}",
                "timestamp": NOW,
            },
            {
                "message_id": "message-2",
                "role": "assistant",
                "content": "I can help",
                "timestamp": NOW + 1,
            },
        ]
    }
    repository = AsyncMock()
    repository.find_context_archive_document_by_id.return_value = deepcopy(raw)
    service = ExtractionArchivePreprocessingService(AsyncMock(), repository=repository)

    first = await service.prepare(_task(), _event())
    second = await service.prepare(_task(), _event())

    assert first[0].kind == PipelineTerminalKind.COMPLETE
    assert second[0].kind == PipelineTerminalKind.COMPLETE
    assert first[1] is not None and second[1] is not None
    first_dump = first[1].model_dump(mode="json")
    second_dump = second[1].model_dump(mode="json")
    assert first_dump == second_dump
    assert first_dump["messages"][0]["content"] == "I am Alice; [REDACTED_SECRET]"
    assert secret not in str(first_dump)
    assert "raw_content" not in str(first_dump)
    assert "normalized_content" not in str(first_dump)
    assert first_dump["archive_id"] == "archive-1"
    assert first_dump["user_id"] == "user-1"
    assert first_dump["session_id"] == "session-1"
    assert [message["message_id"] for message in first_dump["messages"]] == [
        "message-1",
        "message-2",
    ]
    assert [message["role"] for message in first_dump["messages"]] == ["user", "assistant"]
    assert [message["timestamp"] for message in first_dump["messages"]] == [NOW, NOW + 1]
    assert "first_person" not in str(first_dump)
    assert secret not in caplog.text
