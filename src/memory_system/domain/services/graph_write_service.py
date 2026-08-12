"""EXT-006 graph write orchestration service."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Protocol

import structlog
from pydantic import ValidationError
from pymongo import AsyncMongoClient

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.domain.models.entity_alignment import EntityAlignmentSuccess
from memory_system.domain.models.extraction_llm import ExtractionValidatedResult
from memory_system.domain.models.graph_write import (
    GraphWriteAbort,
    GraphWriteFailure,
    GraphWriteInput,
    GraphWriteOutcome,
    GraphWriteOutcomeKind,
    GraphWriteSuccess,
    ImmutableGraphWritePlan,
)
from memory_system.domain.models.reconciliation import ReconciliationSuccess
from memory_system.domain.ports.tokenize_client import TokenizeClient
from memory_system.domain.services.graph_write_plan_builder import build_graph_write_plan
from memory_system.infrastructure.mongodb import extraction_task_repository as task_repo
from memory_system.infrastructure.mongodb.context_archive_message_timestamp_repository import (
    ContextArchiveMessageTimestampRepository,
    GraphWriteAbortError,
)
from memory_system.infrastructure.mongodb.context_archive_repository import (
    find_context_archive_by_id,
)
from memory_system.settings.models import Settings

_logger = structlog.get_logger(__name__)

ServerTimeProvider = Callable[[], int]


class EvidenceLookupReadRepository(Protocol):
    async def find_processed_evidence_ids(
        self, user_id: str, evidence_ids: list[str]
    ) -> set[str]: ...


class GraphWriteWriteRepository(Protocol):
    async def write(self, plan: ImmutableGraphWritePlan) -> None: ...


def _collect_planned_evidence_ids(reconciliation: ReconciliationSuccess) -> list[str]:
    evidence_ids: list[str] = []
    for create_plan in reconciliation.new_memory_create_plans:
        evidence_ids.extend(create_plan.contributing_evidence_ids)
    for update_plan in reconciliation.existing_memory_update_plans:
        evidence_ids.extend(update_plan.contributing_evidence_ids)
    return evidence_ids


class GraphWriteService:
    """Atomic Neo4j graph write library service for EXT-006."""

    def __init__(
        self,
        evidence_repository: EvidenceLookupReadRepository,
        write_repository: GraphWriteWriteRepository,
        *,
        tokenize_client: TokenizeClient,
        settings: Settings,
        archive_timestamp_repository: ContextArchiveMessageTimestampRepository | None = None,
        server_time_provider: ServerTimeProvider | None = None,
    ) -> None:
        self._evidence_repository = evidence_repository
        self._write_repository = write_repository
        self._tokenize_client = tokenize_client
        self._settings = settings
        self._archive_timestamp_repository = archive_timestamp_repository or (
            ContextArchiveMessageTimestampRepository()
        )
        self._server_time_provider = server_time_provider or (lambda: int(time.time()))

    async def write(
        self,
        graph_input: GraphWriteInput,
        *,
        mongodb: AsyncMongoClient[Any],
        attempt_count: int | None = None,
    ) -> GraphWriteOutcome | GraphWriteAbort:
        precondition_abort = self._validate_preconditions(graph_input)
        if precondition_abort is not None:
            return precondition_abort

        if graph_input.session_id is None:
            return GraphWriteAbort()

        reconciliation = graph_input.reconciliation
        evidence_ids = _collect_planned_evidence_ids(reconciliation)
        skipped_graph_write = False

        if evidence_ids:
            processed = await self._evidence_repository.find_processed_evidence_ids(
                graph_input.user_id,
                evidence_ids,
            )
            if len(processed) == len(set(evidence_ids)):
                skipped_graph_write = True

        try:
            plan_or_outcome = await build_graph_write_plan(
                graph_input,
                mongodb=mongodb,
                tokenize_client=self._tokenize_client,
                archive_timestamp_repository=self._archive_timestamp_repository,
                prompt_version=self._settings.memory_extraction.prompt_version,
                max_search_text_tokens=self._settings.memory_extraction.max_search_text_tokens,
                server_time_provider=self._server_time_provider,
            )
        except GraphWriteAbortError:
            return GraphWriteAbort()

        if isinstance(plan_or_outcome, GraphWriteOutcome):
            self._log_failure(
                graph_input,
                plan_or_outcome.failure,
                attempt_count=attempt_count,
            )
            return plan_or_outcome

        plan = plan_or_outcome
        if not skipped_graph_write:
            try:
                await self._write_repository.write(plan)
            except Exception:
                self._log_failure(
                    graph_input,
                    GraphWriteFailure(error_code="graph_write_failed"),
                    attempt_count=attempt_count,
                )
                return GraphWriteOutcome(
                    outcome=GraphWriteOutcomeKind.FAILURE,
                    success=None,
                    failure=GraphWriteFailure(error_code="graph_write_failed"),
                )

        return GraphWriteOutcome(
            outcome=GraphWriteOutcomeKind.SUCCESS,
            success=GraphWriteSuccess(
                user_id=graph_input.user_id,
                archive_id=graph_input.archive_id,
                skipped_graph_write=skipped_graph_write,
                index_sync_memory_set=list(plan.index_sync_memory_set),
            ),
            failure=None,
        )

    async def load_from_persisted_task(
        self,
        mongodb: AsyncMongoClient[Any],
        archive_id: str,
        *,
        entity_alignment_success: EntityAlignmentSuccess,
        reconciliation_success: ReconciliationSuccess,
    ) -> GraphWriteOutcome | GraphWriteAbort:
        task = await task_repo.find_extraction_task_by_archive_id(mongodb, archive_id)
        if task is None:
            return GraphWriteAbort()
        if task.status != ExtractionTaskStatus.PROCESSING or task.extraction_result is None:
            return GraphWriteAbort()
        try:
            validated = ExtractionValidatedResult.model_validate(task.extraction_result)
        except ValidationError:
            return GraphWriteAbort()

        archive = await find_context_archive_by_id(mongodb, archive_id)
        session_id = archive.session_id if archive is not None else None

        graph_input = GraphWriteInput(
            task_id=task.task_id,
            archive_id=task.archive_id,
            user_id=task.user_id,
            session_id=session_id,
            extraction_result=validated,
            entity_alignment=entity_alignment_success,
            reconciliation=reconciliation_success,
        )
        return await self.write(graph_input, mongodb=mongodb, attempt_count=task.attempt_count)

    def _validate_preconditions(self, graph_input: GraphWriteInput) -> GraphWriteAbort | None:
        if graph_input.entity_alignment.user_id != graph_input.user_id:
            return GraphWriteAbort()
        if graph_input.reconciliation.user_id != graph_input.user_id:
            return GraphWriteAbort()
        if graph_input.reconciliation.archive_id != graph_input.archive_id:
            return GraphWriteAbort()
        if graph_input.extraction_result.is_both_empty():
            return GraphWriteAbort()
        return None

    def _log_failure(
        self,
        graph_input: GraphWriteInput,
        failure: GraphWriteFailure | None,
        *,
        attempt_count: int | None,
    ) -> None:
        if failure is None:
            return
        log_kwargs: dict[str, str | int] = {
            "task_id": graph_input.task_id,
            "archive_id": graph_input.archive_id,
            "user_id": graph_input.user_id,
            "failed_stage": failure.failed_stage,
            "error_code": failure.error_code,
        }
        if graph_input.session_id is not None:
            log_kwargs["session_id"] = graph_input.session_id
        if attempt_count is not None:
            log_kwargs["attempt_count"] = attempt_count
        _logger.warning("graph write failed", **log_kwargs)


def create_graph_write_service(
    driver: Any,
    *,
    tokenize_client: TokenizeClient,
    settings: Settings,
    server_time_provider: ServerTimeProvider | None = None,
) -> GraphWriteService:
    from memory_system.infrastructure.neo4j.evidence_lookup_repository import (
        EvidenceLookupRepository,
    )
    from memory_system.infrastructure.neo4j.graph_write_repository import GraphWriteRepository

    return GraphWriteService(
        EvidenceLookupRepository(driver),
        GraphWriteRepository(driver),
        tokenize_client=tokenize_client,
        settings=settings,
        server_time_provider=server_time_provider,
    )
