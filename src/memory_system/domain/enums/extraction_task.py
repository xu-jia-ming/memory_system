"""Memory extraction task status enumerations (§2.1.3)."""

from __future__ import annotations

from enum import StrEnum


class ExtractionTaskStatus(StrEnum):
    """Exact §2.1.3 status literals."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineTerminalKind(StrEnum):
    """Pipeline Port terminal decision kinds (EXT-001 C7)."""

    COMPLETE = "complete"
    FAIL = "fail"
    ABORT_WITHOUT_TERMINAL = "abort_without_terminal"
