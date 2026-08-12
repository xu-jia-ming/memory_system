from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus, PipelineTerminalKind
from memory_system.domain.models.archive_created_event import ArchiveCreatedEvent
from memory_system.domain.models.extraction_task import MemoryExtractionTask
from memory_system.domain.services.extraction_archive_preprocessing_service import (
    ExtractionArchivePreprocessingService,
    normalize_content,
    validate_raw_archive,
)

NOW = 1_700_000_000


def _document() -> dict[str, Any]:
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
                "content": " Ｐassword: secret  \n\n next",
                "timestamp": NOW,
            },
            {
                "message_id": "message-2",
                "role": "assistant",
                "content": "",
                "timestamp": NOW,
            },
        ],
        "created_time": NOW,
    }


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


def test_normalization_is_nfkc_trim_and_whitespace_deterministic() -> None:
    assert normalize_content(" Ａ  B \n\n\n C ") == "A B\nC"


def test_RAW_01_complete_valid_archive_preserves_types_order_and_empty_messages() -> None:
    archive = validate_raw_archive(_document(), "archive-1")
    assert type(archive.archive_id) is str
    assert type(archive.base_compression_version) is int
    assert type(archive.messages) is list
    assert [message.message_id for message in archive.messages] == ["message-1", "message-2"]
    empty = _document() | {"messages": []}
    assert validate_raw_archive(empty, "archive-1").messages == []


@pytest.mark.parametrize(
    "field",
    [
        "archive_id",
        "user_id",
        "session_id",
        "archive_batch_key",
        "base_compression_version",
        "messages",
        "created_time",
    ],
    ids=[f"RAW-02-{field}" for field in (
        "archive_id",
        "user_id",
        "session_id",
        "archive_batch_key",
        "base_compression_version",
        "messages",
        "created_time",
    )],
)
def test_RAW_02_missing_or_null_required_top_level_field_is_rejected(field: str) -> None:
    missing = _document()
    del missing[field]
    with pytest.raises(ValueError):
        validate_raw_archive(missing, "archive-1")
    null = _document()
    null[field] = None
    with pytest.raises(ValueError):
        validate_raw_archive(null, "archive-1")


def test_RAW_03_empty_identity_is_rejected_but_empty_content_is_valid() -> None:
    for field in ("archive_id", "user_id", "session_id", "archive_batch_key"):
        document = _document()
        document[field] = ""
        with pytest.raises(ValueError):
            validate_raw_archive(document, "archive-1")
    message_id = _document()
    message_id["messages"][0]["message_id"] = ""
    with pytest.raises(ValueError):
        validate_raw_archive(message_id, "archive-1")
    empty_content = _document()
    empty_content["messages"][0]["content"] = ""
    assert validate_raw_archive(empty_content, "archive-1").messages[0].content == ""


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("archive_id", 1),
        ("user_id", {}),
        ("session_id", []),
        ("archive_batch_key", 1.0),
        ("base_compression_version", "0"),
        ("messages", {}),
        ("created_time", "now"),
    ],
    ids=[f"RAW-04-{field}" for field in (
        "archive_id",
        "user_id",
        "session_id",
        "archive_batch_key",
        "base_compression_version",
        "messages",
        "created_time",
    )],
)
def test_RAW_04_top_level_wrong_types_are_not_coerced(field: str, value: object) -> None:
    document = _document()
    document[field] = value
    with pytest.raises(ValueError):
        validate_raw_archive(document, "archive-1")


@pytest.mark.parametrize("value", [True, False, 1.5, "1", "2024-01-01T00:00:00Z"])
def test_RAW_05_integer_fields_reject_bool_float_string_and_datetime_like(value: object) -> None:
    for field in ("base_compression_version", "created_time"):
        document = _document()
        document[field] = value
        with pytest.raises(ValueError):
            validate_raw_archive(document, "archive-1")


@pytest.mark.parametrize("messages", [None, {}, "message", [None], [1], [{}]])
def test_RAW_06_malformed_message_collection_is_rejected_without_partial_output(
    messages: object,
) -> None:
    document = _document()
    document["messages"] = messages
    with pytest.raises(ValueError):
        validate_raw_archive(document, "archive-1")


@pytest.mark.parametrize("field", ["message_id", "role", "content", "timestamp"])
def test_RAW_07_message_missing_null_or_wrong_field_type_is_rejected(field: str) -> None:
    document = _document()
    del document["messages"][0][field]
    with pytest.raises(ValueError):
        validate_raw_archive(document, "archive-1")
    document = _document()
    document["messages"][0][field] = None
    with pytest.raises(ValueError):
        validate_raw_archive(document, "archive-1")


@pytest.mark.parametrize("role", ["USER", "system", 1, {}])
def test_RAW_08_invalid_message_role_is_rejected(role: object) -> None:
    document = _document()
    document["messages"][0]["role"] = role
    with pytest.raises(ValueError):
        validate_raw_archive(document, "archive-1")


def test_RAW_09_unknown_top_level_message_and_nested_fields_are_rejected() -> None:
    for location in ("top", "message"):
        document = _document()
        if location == "top":
            document["unknown"] = True
        else:
            document["messages"][0]["unknown"] = True
        with pytest.raises(ValueError):
            validate_raw_archive(document, "archive-1")
    document = _document()
    document["_id"] = "storage-only"
    assert "_id" not in validate_raw_archive(document, "archive-1").model_dump()


@pytest.mark.parametrize(
    "field",
    [
        "archive_id",
        "user_id",
        "session_id",
        "archive_batch_key",
        "base_compression_version",
        "messages",
        "created_time",
    ],
)
def test_missing_top_level_field_is_rejected_before_model_output(field: str) -> None:
    document = _document()
    del document[field]
    with pytest.raises(ValueError):
        validate_raw_archive(document, "archive-1")


def test_unknown_application_field_rejected_but_storage_id_ignored() -> None:
    document = _document()
    document["_id"] = "storage-id"
    archive = validate_raw_archive(document, "archive-1")
    assert not hasattr(archive, "_id")
    document["unexpected"] = True
    with pytest.raises(ValueError):
        validate_raw_archive(document, "archive-1")


@pytest.mark.asyncio
async def test_invalid_later_message_prevents_any_ready_output() -> None:
    document = _document()
    document["messages"] = [
        document["messages"][0],
        {"message_id": "bad", "role": "user", "content": 7, "timestamp": NOW},
    ]
    repository = AsyncMock()
    repository.find_context_archive_document_by_id.return_value = document
    service = ExtractionArchivePreprocessingService(AsyncMock(), repository=repository)
    decision, ready = await service.prepare(_task(), _event())
    assert decision.kind == PipelineTerminalKind.FAIL
    assert decision.last_error is not None
    assert decision.last_error.error_code == "invalid_archive"
    assert ready is None


@pytest.mark.asyncio
async def test_RAW_10_lookup_uses_event_archive_id_only() -> None:
    repository = AsyncMock()
    repository.find_context_archive_document_by_id.return_value = _document()
    service = ExtractionArchivePreprocessingService(AsyncMock(), repository=repository)
    await service.prepare(_task(), _event())
    repository.find_context_archive_document_by_id.assert_awaited_once_with(
        service._mongodb, "archive-1"
    )


@pytest.mark.asyncio
async def test_RAW_11_missing_archive_is_archive_read_failure() -> None:
    repository = AsyncMock()
    repository.find_context_archive_document_by_id.return_value = None
    service = ExtractionArchivePreprocessingService(AsyncMock(), repository=repository)
    decision, ready = await service.prepare(_task(), _event())
    assert decision.last_error is not None
    assert decision.last_error.error_code == "archive_not_found"
    assert decision.last_error.failed_stage == "archive_read"
    assert ready is None


@pytest.mark.asyncio
async def test_RAW_12_full_validation_precedes_token_normalization_redaction_and_output() -> None:
    document = _document()
    document["messages"][1]["content"] = 7
    repository = AsyncMock()
    repository.find_context_archive_document_by_id.return_value = document
    redactor = Mock()
    service = ExtractionArchivePreprocessingService(
        AsyncMock(), repository=repository, redactor=redactor
    )
    with patch(
        "memory_system.domain.services.extraction_archive_preprocessing_service.estimate_tokens"
    ) as estimator, patch(
        "memory_system.domain.services.extraction_archive_preprocessing_service.normalize_content"
    ) as normalizer:
        decision, ready = await service.prepare(_task(), _event())
    assert decision.last_error is not None
    assert decision.last_error.error_code == "invalid_archive"
    assert ready is None
    estimator.assert_not_called()
    normalizer.assert_not_called()
    redactor.redact.assert_not_called()


@pytest.mark.asyncio
async def test_RED_25_ownership_and_token_overflow_fail_before_redaction() -> None:
    ownership_event = _event().model_copy(update={"user_id": "other-user"})
    repository = AsyncMock()
    repository.find_context_archive_document_by_id.return_value = _document()
    redactor = Mock()
    service = ExtractionArchivePreprocessingService(
        AsyncMock(), repository=repository, redactor=redactor
    )
    decision, ready = await service.prepare(_task(), ownership_event)
    assert decision.last_error is not None
    assert decision.last_error.error_code == "archive_ownership_mismatch"
    assert ready is None
    redactor.redact.assert_not_called()

    service = ExtractionArchivePreprocessingService(
        AsyncMock(), max_archive_estimated_tokens=0, repository=repository, redactor=redactor
    )
    decision, ready = await service.prepare(_task(), _event())
    assert decision.last_error is not None
    assert decision.last_error.error_code == "archive_too_large"
    assert ready is None


@pytest.mark.asyncio
async def test_RED_26_empty_archive_completes_without_redaction() -> None:
    repository = AsyncMock()
    repository.find_context_archive_document_by_id.return_value = _document() | {"messages": []}
    redactor = Mock()
    service = ExtractionArchivePreprocessingService(
        AsyncMock(), repository=repository, redactor=redactor
    )
    decision, ready = await service.prepare(_task(), _event())
    assert decision.kind == PipelineTerminalKind.COMPLETE
    assert ready is not None
    assert ready.messages == []
    redactor.redact.assert_not_called()


@pytest.mark.asyncio
async def test_valid_archive_only_exposes_normalized_redacted_handoff() -> None:
    repository = AsyncMock()
    repository.find_context_archive_document_by_id.return_value = _document()
    service = ExtractionArchivePreprocessingService(AsyncMock(), repository=repository)
    decision, ready = await service.prepare(_task(), _event())
    assert decision.kind == PipelineTerminalKind.COMPLETE
    assert ready is not None
    assert ready.messages[0].content == "[REDACTED_SECRET]\nnext"
    assert ready.messages[1].content == ""
    assert ready.messages[0].message_id == "message-1"


@pytest.mark.asyncio
async def test_missing_archive_maps_to_archive_read() -> None:
    repository = AsyncMock()
    repository.find_context_archive_document_by_id.return_value = None
    service = ExtractionArchivePreprocessingService(AsyncMock(), repository=repository)
    decision = await service.run(_task(), _event())
    assert decision.last_error is not None
    assert decision.last_error.error_code == "archive_not_found"
    assert decision.last_error.failed_stage == "archive_read"


@pytest.mark.asyncio
async def test_repository_failure_aborts_without_terminal() -> None:
    repository = AsyncMock()
    repository.find_context_archive_document_by_id.side_effect = RuntimeError("db down")
    service = ExtractionArchivePreprocessingService(AsyncMock(), repository=repository)
    decision = await service.run(_task(), _event())
    assert decision.kind == PipelineTerminalKind.ABORT_WITHOUT_TERMINAL
