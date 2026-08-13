"""RET-003 pure validation helpers for Neo4j authoritative memory readback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from memory_system.domain.models.retrieval_memory_snapshot import RetrievalMemorySnapshot

VALID_MEMORY_TYPES = frozenset({"fact", "preference", "event", "profile"})


def memory_status_allowed(
    status: str,
    *,
    include_conflicted: bool,
    include_history: bool,
) -> bool:
    if not include_conflicted and not include_history:
        return status == "active"
    if include_conflicted and not include_history:
        return status in {"active", "conflicted"}
    if not include_conflicted and include_history:
        return status in {"active", "superseded"}
    return status in {"active", "conflicted", "superseded"}


def memory_type_allowed(memory_type: str, memory_types: list[str] | None) -> bool:
    if not memory_types:
        return True
    return memory_type in memory_types


@dataclass(frozen=True, slots=True)
class MemoryValidationResult:
    valid: bool
    rejection_reason: Literal["wrong_user", "type_or_status"] | None = None


def validate_memory_for_request(
    snapshot: RetrievalMemorySnapshot,
    user_id: str,
    memory_types: list[str] | None,
    *,
    include_conflicted: bool,
    include_history: bool,
) -> MemoryValidationResult:
    if snapshot.user_id != user_id:
        return MemoryValidationResult(valid=False, rejection_reason="wrong_user")
    if not memory_type_allowed(snapshot.memory_type, memory_types):
        return MemoryValidationResult(valid=False, rejection_reason="type_or_status")
    if not memory_status_allowed(
        snapshot.status,
        include_conflicted=include_conflicted,
        include_history=include_history,
    ):
        return MemoryValidationResult(valid=False, rejection_reason="type_or_status")
    return MemoryValidationResult(valid=True)


def normalize_memory_types(memory_types: list[str] | None) -> list[str] | None:
    if memory_types is None:
        return None
    deduped = sorted(set(memory_types))
    if not deduped:
        return None
    invalid = [item for item in deduped if item not in VALID_MEMORY_TYPES]
    if invalid:
        raise ValueError(f"invalid memory_types: {invalid}")
    return deduped
