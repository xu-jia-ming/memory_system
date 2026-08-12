"""EXT-002 strict Archive read, preprocessing, and redaction gate."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Any, Protocol

from pydantic import ValidationError
from pymongo import AsyncMongoClient

from memory_system.domain.models.archive_created_event import ArchiveCreatedEvent
from memory_system.domain.models.extraction_preprocessing import (
    ExtractionArchiveMessage,
    ExtractionReadyArchive,
    ValidatedRawArchive,
)
from memory_system.domain.models.extraction_task import (
    ExtractionLastError,
    MemoryExtractionTask,
)
from memory_system.domain.services.extraction_pipeline_port import (
    ExtractionPipelinePort,
    PipelineTerminalDecision,
)
from memory_system.domain.services.extraction_redaction_service import (
    ExtractionRedactionService,
    RedactionFailure,
)
from memory_system.domain.services.token_estimator import estimate_tokens
from memory_system.infrastructure.mongodb import context_archive_repository

_TOP_LEVEL_FIELDS = frozenset(
    {
        "archive_id",
        "user_id",
        "session_id",
        "archive_batch_key",
        "base_compression_version",
        "messages",
        "created_time",
    }
)
_MESSAGE_FIELDS = frozenset({"message_id", "role", "content", "timestamp"})
_HORIZONTAL_SPACE = re.compile(r"[ \t\f\v]+")
_BLANK_LINES = re.compile(r"\n(?:[ \t]*\n)+")
_NEWLINE_PADDING = re.compile(r"[ \t]*\n[ \t]*")


class InvalidArchiveError(ValueError):
    """Expected strict raw-document validation failure."""


class ArchiveDocumentReader(Protocol):
    async def find_context_archive_document_by_id(
        self, mongodb: AsyncMongoClient[Any], archive_id: str
    ) -> Mapping[str, Any] | None: ...


def normalize_content(content: str) -> str:
    """Apply only the approved deterministic textual normalization."""
    normalized = unicodedata.normalize("NFKC", content)
    normalized = _HORIZONTAL_SPACE.sub(" ", normalized)
    normalized = _BLANK_LINES.sub("\n", normalized)
    normalized = _NEWLINE_PADDING.sub("\n", normalized)
    return normalized.strip()


def _is_actual_int(value: object) -> bool:
    return type(value) is int


def _validate_mapping_shape(raw: Mapping[str, Any]) -> dict[str, Any]:
    keys = set(raw)
    if "_id" in keys:
        keys.remove("_id")
    if keys != _TOP_LEVEL_FIELDS:
        raise InvalidArchiveError("archive fields are invalid")
    messages = raw["messages"]
    if type(messages) is not list:
        raise InvalidArchiveError("archive messages are invalid")
    for message in messages:
        if not isinstance(message, Mapping):
            raise InvalidArchiveError("archive message is invalid")
        if set(message) != _MESSAGE_FIELDS:
            raise InvalidArchiveError("archive message fields are invalid")
        if type(message["message_id"]) is not str or not message["message_id"]:
            raise InvalidArchiveError("archive message identity is invalid")
        if type(message["role"]) is not str or message["role"] not in {"user", "assistant"}:
            raise InvalidArchiveError("archive message role is invalid")
        if type(message["content"]) is not str:
            raise InvalidArchiveError("archive message content is invalid")
        if not _is_actual_int(message["timestamp"]):
            raise InvalidArchiveError("archive message timestamp is invalid")
    for field in ("archive_id", "user_id", "session_id", "archive_batch_key"):
        if type(raw[field]) is not str or not raw[field]:
            raise InvalidArchiveError("archive identity is invalid")
    if not _is_actual_int(raw["base_compression_version"]):
        raise InvalidArchiveError("archive compression version is invalid")
    if not _is_actual_int(raw["created_time"]):
        raise InvalidArchiveError("archive created time is invalid")
    document = dict(raw)
    document.pop("_id", None)
    return document


def validate_raw_archive(raw: object, event_archive_id: str) -> ValidatedRawArchive:
    """Complete the strict structural gate before creating any archive model."""
    if not isinstance(raw, Mapping):
        raise InvalidArchiveError("archive document is invalid")
    document = _validate_mapping_shape(raw)
    if document["archive_id"] != event_archive_id:
        raise InvalidArchiveError("archive identifier does not match event")
    try:
        return ValidatedRawArchive.model_validate(document)
    except ValidationError as exc:
        raise InvalidArchiveError("archive model validation failed") from exc


def _error(error_code: str, failed_stage: str, message: str) -> PipelineTerminalDecision:
    return PipelineTerminalDecision.fail(
        ExtractionLastError(
            error_code=error_code,
            failed_stage=failed_stage,
            message=message,
        )
    )


class ExtractionArchivePreprocessingService(ExtractionPipelinePort):
    """Read and prepare an Archive without task or offset side effects."""

    def __init__(
        self,
        mongodb: AsyncMongoClient[Any],
        *,
        max_archive_estimated_tokens: int = 8000,
        redactor: ExtractionRedactionService | None = None,
        repository: ArchiveDocumentReader = context_archive_repository,
    ) -> None:
        self._mongodb = mongodb
        self._max_archive_estimated_tokens = max_archive_estimated_tokens
        self._redactor = redactor or ExtractionRedactionService()
        self._repository = repository
        self.last_ready_archive: ExtractionReadyArchive | None = None

    async def prepare(
        self, task: MemoryExtractionTask, event: ArchiveCreatedEvent
    ) -> tuple[PipelineTerminalDecision, ExtractionReadyArchive | None]:
        try:
            raw = await self._repository.find_context_archive_document_by_id(
                self._mongodb, event.archive_id
            )
        except Exception:
            return PipelineTerminalDecision.abort_without_terminal(), None
        if raw is None:
            return _error("archive_not_found", "archive_read", "archive was not found"), None

        try:
            archive = validate_raw_archive(raw, event.archive_id)
        except InvalidArchiveError:
            return _error("invalid_archive", "archive_validate", "archive failed validation"), None
        except Exception:
            return PipelineTerminalDecision.abort_without_terminal(), None

        if archive.user_id != event.user_id or archive.user_id != task.user_id:
            return (
                _error(
                    "archive_ownership_mismatch",
                    "archive_validate",
                    "archive ownership did not match",
                ),
                None,
            )
        if archive.session_id != event.session_id:
            return (
                _error(
                    "archive_ownership_mismatch",
                    "archive_validate",
                    "archive session did not match",
                ),
                None,
            )
        try:
            estimated_tokens = sum(estimate_tokens(message.content) for message in archive.messages)
        except Exception:
            return PipelineTerminalDecision.abort_without_terminal(), None
        if estimated_tokens > self._max_archive_estimated_tokens:
            return (
                _error("archive_too_large", "archive_validate", "archive exceeded token limit"),
                None,
            )

        try:
            ready_messages = [
                ExtractionArchiveMessage(
                    message_id=message.message_id,
                    role=message.role,
                    content=self._redactor.redact(normalize_content(message.content)),
                    timestamp=message.timestamp,
                )
                for message in archive.messages
            ]
        except RedactionFailure:
            return _error("redaction_failed", "redaction", "archive redaction failed"), None
        except Exception:
            return PipelineTerminalDecision.abort_without_terminal(), None

        try:
            ready = ExtractionReadyArchive(
                archive_id=archive.archive_id,
                user_id=archive.user_id,
                session_id=archive.session_id,
                messages=ready_messages,
            )
        except Exception:
            return PipelineTerminalDecision.abort_without_terminal(), None
        return PipelineTerminalDecision.complete(), ready

    async def run(
        self, task: MemoryExtractionTask, event: ArchiveCreatedEvent
    ) -> PipelineTerminalDecision:
        decision, ready = await self.prepare(task, event)
        self.last_ready_archive = ready
        return decision
