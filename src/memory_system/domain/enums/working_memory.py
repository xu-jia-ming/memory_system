"""Working Memory enumerations aligned with §1.2.1."""

from __future__ import annotations

from enum import StrEnum


class SessionStatus(StrEnum):
    ACTIVE = "active"
    CLOSING = "closing"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
