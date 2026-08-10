"""Redis Hash field codec for WorkingMemoryMeta (§1.2.1)."""

from __future__ import annotations

from collections.abc import Mapping

from memory_system.domain.enums.working_memory import SessionStatus
from memory_system.domain.models.working_memory import WorkingMemoryMeta

META_HASH_FIELD_NAMES: tuple[str, ...] = (
    "user_id",
    "session_id",
    "compressed_context",
    "estimated_tokens",
    "compression_version",
    "status",
    "pending_archive_id",
    "pending_archive_batch_key",
    "pending_archive_message_count",
    "pending_archive_estimated_tokens",
    "created_time",
    "updated_time",
)


def _encode_optional_str(value: str | None) -> str:
    return "" if value is None else value


def _decode_optional_str(value: str) -> str | None:
    return None if value == "" else value


def meta_to_hash_fields(meta: WorkingMemoryMeta) -> dict[str, str]:
    """Serialize WorkingMemoryMeta to Redis HSET string fields."""
    return {
        "user_id": meta.user_id,
        "session_id": meta.session_id,
        "compressed_context": meta.compressed_context,
        "estimated_tokens": str(meta.estimated_tokens),
        "compression_version": str(meta.compression_version),
        "status": meta.status.value,
        "pending_archive_id": _encode_optional_str(meta.pending_archive_id),
        "pending_archive_batch_key": _encode_optional_str(meta.pending_archive_batch_key),
        "pending_archive_message_count": str(meta.pending_archive_message_count),
        "pending_archive_estimated_tokens": str(meta.pending_archive_estimated_tokens),
        "created_time": str(meta.created_time),
        "updated_time": str(meta.updated_time),
    }


def hash_fields_to_meta(fields: Mapping[str, str]) -> WorkingMemoryMeta:
    """Deserialize Redis HGETALL fields to WorkingMemoryMeta."""
    return WorkingMemoryMeta(
        user_id=fields["user_id"],
        session_id=fields["session_id"],
        compressed_context=fields["compressed_context"],
        estimated_tokens=int(fields["estimated_tokens"]),
        compression_version=int(fields["compression_version"]),
        status=SessionStatus(fields["status"]),
        pending_archive_id=_decode_optional_str(fields["pending_archive_id"]),
        pending_archive_batch_key=_decode_optional_str(fields["pending_archive_batch_key"]),
        pending_archive_message_count=int(fields["pending_archive_message_count"]),
        pending_archive_estimated_tokens=int(fields["pending_archive_estimated_tokens"]),
        created_time=int(fields["created_time"]),
        updated_time=int(fields["updated_time"]),
    )
