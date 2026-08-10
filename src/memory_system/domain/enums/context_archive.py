"""Context archive outcome enumerations (§1.2.2)."""

from __future__ import annotations

from enum import StrEnum


class ContextArchiveOutcome(StrEnum):
    """Stable internal literals for create/reuse results."""

    CREATED = "created"
    REUSED = "reused"
