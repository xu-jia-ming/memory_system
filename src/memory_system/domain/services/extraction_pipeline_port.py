"""Extraction pipeline port and terminal decision types (EXT-001 C7)."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, model_validator

from memory_system.domain.enums.extraction_task import PipelineTerminalKind
from memory_system.domain.models.archive_created_event import ArchiveCreatedEvent
from memory_system.domain.models.extraction_task import ExtractionLastError, MemoryExtractionTask


class PipelineTerminalDecision(BaseModel):
    """Terminal or abort decision returned by ``ExtractionPipelinePort.run``."""

    model_config = ConfigDict(strict=True, extra="forbid")

    kind: PipelineTerminalKind
    last_error: ExtractionLastError | None = None

    @model_validator(mode="after")
    def _validate_fail_requires_last_error(self) -> PipelineTerminalDecision:
        if self.kind == PipelineTerminalKind.FAIL and self.last_error is None:
            raise ValueError("fail decision requires last_error")
        if self.kind != PipelineTerminalKind.FAIL and self.last_error is not None:
            raise ValueError("last_error is only valid for fail decisions")
        return self

    @classmethod
    def complete(cls) -> PipelineTerminalDecision:
        return cls(kind=PipelineTerminalKind.COMPLETE)

    @classmethod
    def fail(cls, last_error: ExtractionLastError) -> PipelineTerminalDecision:
        return cls(kind=PipelineTerminalKind.FAIL, last_error=last_error)

    @classmethod
    def abort_without_terminal(cls) -> PipelineTerminalDecision:
        return cls(kind=PipelineTerminalKind.ABORT_WITHOUT_TERMINAL)


class ExtractionPipelinePort(Protocol):
    """Injectable pipeline boundary; production stages belong to EXT-002+."""

    async def run(
        self,
        task: MemoryExtractionTask,
        event: ArchiveCreatedEvent,
    ) -> PipelineTerminalDecision:
        """Execute or resume extraction for ``task``.

        When ``task.extraction_result`` is non-null, implementations must not
        invoke LLM again (reuse persisted result).
        """
        ...
