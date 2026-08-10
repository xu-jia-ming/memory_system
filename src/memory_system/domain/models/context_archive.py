"""Context Archive domain models aligned with §1.2.2 (schema only; no Mongo I/O)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from memory_system.domain.enums.context_archive import ContextArchiveOutcome
from memory_system.domain.enums.working_memory import MessageRole
from memory_system.domain.models.working_memory import WorkingMemoryMessage


class ContextArchiveMessage(BaseModel):
    """Single archived message element (four fields only; no estimated_tokens)."""

    model_config = ConfigDict(strict=True)

    message_id: str
    role: MessageRole
    content: str
    timestamp: int


class ContextArchive(BaseModel):
    """Full persisted Context Archive document."""

    model_config = ConfigDict(strict=True)

    archive_id: str
    user_id: str
    session_id: str
    archive_batch_key: str
    base_compression_version: int
    messages: list[ContextArchiveMessage]
    created_time: int


class ContextArchiveCreateInput(BaseModel):
    """Input for create_or_reuse_context_archive."""

    model_config = ConfigDict(strict=True)

    user_id: str
    session_id: str
    archive_batch_key: str
    base_compression_version: int = Field(ge=0)
    messages: list[WorkingMemoryMessage]


class ContextArchiveResult(BaseModel):
    """Result of create_or_reuse_context_archive."""

    model_config = ConfigDict(strict=True)

    outcome: ContextArchiveOutcome
    archive_id: str
    archive: ContextArchive


def wm_message_to_archive_message(msg: WorkingMemoryMessage) -> ContextArchiveMessage:
    """Map WorkingMemoryMessage to archive subset (strip estimated_tokens)."""
    return ContextArchiveMessage(
        message_id=msg.message_id,
        role=msg.role,
        content=msg.content,
        timestamp=msg.timestamp,
    )


def archive_messages_from_working_memory(
    messages: list[WorkingMemoryMessage],
) -> list[ContextArchiveMessage]:
    """Map a batch of Working Memory messages to archive messages."""
    return [wm_message_to_archive_message(msg) for msg in messages]


def archive_document_from_input(
    *,
    input: ContextArchiveCreateInput,
    archive_id: str,
    created_time: int,
) -> dict[str, object]:
    """Build BSON-insertable document dict (messages contain four fields only)."""
    archive_messages = archive_messages_from_working_memory(input.messages)
    return {
        "archive_id": archive_id,
        "user_id": input.user_id,
        "session_id": input.session_id,
        "archive_batch_key": input.archive_batch_key,
        "base_compression_version": input.base_compression_version,
        "messages": [msg.model_dump(mode="json") for msg in archive_messages],
        "created_time": created_time,
    }
