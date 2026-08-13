"""Production continuation of the memory extraction pipeline (EXT-009)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, cast

import httpx
from pymongo import AsyncMongoClient

from memory_system.domain.enums.extraction_task import (
    PipelineTerminalKind,
)
from memory_system.domain.models.archive_created_event import ArchiveCreatedEvent
from memory_system.domain.models.entity_alignment import (
    EntityAlignmentAbort,
    EntityAlignmentOutcome,
    EntityAlignmentOutcomeKind,
)
from memory_system.domain.models.extraction_task import (
    ExtractionLastError,
    MemoryExtractionTask,
)
from memory_system.domain.models.graph_write import (
    GraphWriteAbort,
    GraphWriteOutcome,
    GraphWriteOutcomeKind,
    GraphWriteSuccess,
    IndexSyncMemoryEntry,
)
from memory_system.domain.models.reconciliation import (
    ReconciliationAbort,
    ReconciliationOutcome,
    ReconciliationOutcomeKind,
)
from memory_system.domain.models.retrieval_index_sync import (
    RetrievalIndexSyncAbort,
    RetrievalIndexSyncInput,
    RetrievalIndexSyncOutcomeKind,
)
from memory_system.domain.ports.tokenize_client import TokenizeClient
from memory_system.domain.services.core_search_text import build_core_search_text
from memory_system.domain.services.entity_alignment_service import (
    EntityAlignmentService,
    create_entity_alignment_service,
)
from memory_system.domain.services.extraction_llm_service import (
    ExtractionLlmService,
    is_both_empty_extraction_result,
)
from memory_system.domain.services.extraction_pipeline_port import (
    ExtractionPipelinePort,
    PipelineTerminalDecision,
)
from memory_system.domain.services.graph_write_service import (
    GraphWriteService,
    create_graph_write_service,
)
from memory_system.domain.services.reconciliation_service import (
    ReconciliationService,
    create_reconciliation_service,
)
from memory_system.domain.services.retrieval_index_sync_service import (
    RetrievalIndexSyncService,
    create_retrieval_index_sync_service,
)
from memory_system.infrastructure.embedding import create_embedding_client
from memory_system.infrastructure.embedding.types import EmbeddingClient
from memory_system.infrastructure.llm.deepseek_client import DeepSeekLlmClient
from memory_system.infrastructure.llm.protocol import LLMClient
from memory_system.infrastructure.mongodb import extraction_task_repository as task_repo
from memory_system.infrastructure.neo4j.retrieval_index_read_repository import (
    RetrievalIndexReadRepository,
)
from memory_system.infrastructure.tei.tei_tokenize_client import TeiTokenizeClient
from memory_system.settings.models import Settings

Clock = Callable[[], int]
BeforeRetrievalSyncHook = Callable[[GraphWriteSuccess], Awaitable[None] | None]
ReplayIndexSyncMemorySetLoader = Callable[[str, str], Awaitable[list[IndexSyncMemoryEntry]]]

_REPLAY_INDEX_SYNC_MEMORY_IDS_CYPHER = """
MATCH (ev:Evidence)-[:SUPPORTS]->(memory:Memory)
WHERE ev.archive_id = $archive_id
  AND ev.user_id = $user_id
  AND memory.user_id = $user_id
RETURN DISTINCT memory.memory_id AS memory_id
""".strip()


async def _load_replay_index_sync_memory_ids(
    neo4j_driver: Any,
    *,
    user_id: str,
    archive_id: str,
) -> set[str]:
    """Recover durable archive-supported memories after a skipped graph replay."""

    async def _read(tx: Any) -> set[str]:
        result = await tx.run(
            _REPLAY_INDEX_SYNC_MEMORY_IDS_CYPHER,
            archive_id=archive_id,
            user_id=user_id,
        )
        memory_ids: set[str] = set()
        async for record in result:
            memory_id = record.get("memory_id")
            if not isinstance(memory_id, str):
                raise RuntimeError("replay index sync memory_id must be a string")
            memory_ids.add(memory_id)
        return memory_ids

    async with neo4j_driver.session() as session:
        return cast(set[str], await session.execute_read(_read))


async def _load_replay_index_sync_memory_set(
    neo4j_driver: Any,
    tokenize_client: TokenizeClient,
    *,
    user_id: str,
    archive_id: str,
) -> list[IndexSyncMemoryEntry]:
    memory_ids = await _load_replay_index_sync_memory_ids(
        neo4j_driver,
        user_id=user_id,
        archive_id=archive_id,
    )
    if not memory_ids:
        return []

    rows = await RetrievalIndexReadRepository(neo4j_driver).load_memory_index_rows(
        user_id,
        memory_ids,
    )
    if {row.memory_id for row in rows} != memory_ids:
        raise RuntimeError("replay index sync memory rows missing")

    entries: list[IndexSyncMemoryEntry] = []
    for row in sorted(rows, key=lambda item: item.memory_id):
        core_search_text = build_core_search_text(
            user_id=user_id,
            content=row.content,
            subject_entity_id=row.subject_entity_id,
            subject_canonical_name=row.subject_canonical_name or "",
            predicate=row.predicate,
            object_entity_id=row.object_entity_id,
            object_canonical_name=row.object_canonical_name,
            object_value=row.object_value,
        )
        token_count = await tokenize_client.count_tokens(core_search_text)
        entries.append(
            IndexSyncMemoryEntry(
                memory_id=row.memory_id,
                core_search_text=core_search_text,
                token_count=token_count,
            )
        )
    return entries


class ProductionExtractionPipeline(ExtractionPipelinePort):
    """Orchestrate the existing EXT-003 through EXT-007 stage services."""

    def __init__(
        self,
        mongodb: AsyncMongoClient[Any],
        extraction_llm_service: ExtractionLlmService,
        entity_alignment_service: EntityAlignmentService,
        reconciliation_service: ReconciliationService,
        graph_write_service: GraphWriteService,
        retrieval_index_sync_service: RetrievalIndexSyncService,
        *,
        before_retrieval_sync_hook: BeforeRetrievalSyncHook | None = None,
        replay_index_sync_memory_set_loader: ReplayIndexSyncMemorySetLoader | None = None,
    ) -> None:
        self._mongodb = mongodb
        self._extraction_llm_service = extraction_llm_service
        self._entity_alignment_service = entity_alignment_service
        self._reconciliation_service = reconciliation_service
        self._graph_write_service = graph_write_service
        self._retrieval_index_sync_service = retrieval_index_sync_service
        self._before_retrieval_sync_hook = before_retrieval_sync_hook
        self._replay_index_sync_memory_set_loader = replay_index_sync_memory_set_loader

    async def run(
        self,
        task: MemoryExtractionTask,
        event: ArchiveCreatedEvent,
    ) -> PipelineTerminalDecision:
        current_task = task

        if current_task.extraction_result is None:
            llm_decision = await self._extraction_llm_service.run(current_task, event)
            if llm_decision.kind != PipelineTerminalKind.ABORT_WITHOUT_TERMINAL:
                return llm_decision

            reloaded = await task_repo.find_extraction_task_by_archive_id(
                self._mongodb,
                current_task.archive_id,
            )
            if reloaded is None or reloaded.extraction_result is None:
                return PipelineTerminalDecision.abort_without_terminal()
            current_task = reloaded

        if current_task.extraction_result is None:
            return PipelineTerminalDecision.abort_without_terminal()
        if is_both_empty_extraction_result(current_task.extraction_result):
            return PipelineTerminalDecision.complete()

        alignment = await self._entity_alignment_service.load_from_persisted_task(
            self._mongodb,
            current_task.archive_id,
        )
        if isinstance(alignment, EntityAlignmentAbort):
            return PipelineTerminalDecision.abort_without_terminal()
        if alignment.outcome == EntityAlignmentOutcomeKind.FAILURE:
            return self._alignment_failure_decision(alignment)
        if alignment.success is None:
            return PipelineTerminalDecision.abort_without_terminal()
        alignment_success = alignment.success

        reconciliation = await self._reconciliation_service.load_from_persisted_task(
            self._mongodb,
            current_task.archive_id,
            entity_alignment_success=alignment_success,
        )
        if isinstance(reconciliation, ReconciliationAbort):
            return PipelineTerminalDecision.abort_without_terminal()
        if reconciliation.outcome == ReconciliationOutcomeKind.FAILURE:
            return self._reconciliation_failure_decision(reconciliation)
        if reconciliation.success is None:
            return PipelineTerminalDecision.abort_without_terminal()
        reconciliation_success = reconciliation.success

        graph_write = await self._graph_write_service.load_from_persisted_task(
            self._mongodb,
            current_task.archive_id,
            entity_alignment_success=alignment_success,
            reconciliation_success=reconciliation_success,
        )
        if isinstance(graph_write, GraphWriteAbort):
            return PipelineTerminalDecision.abort_without_terminal()
        if graph_write.outcome == GraphWriteOutcomeKind.FAILURE:
            return self._graph_write_failure_decision(graph_write)
        if graph_write.success is None:
            return PipelineTerminalDecision.abort_without_terminal()
        graph_write_success = graph_write.success

        if self._before_retrieval_sync_hook is not None:
            hook_result = self._before_retrieval_sync_hook(graph_write_success)
            if hook_result is not None:
                await hook_result

        repaired_graph_write_success = await self._repair_empty_replay_index_sync_set(
            graph_write_success,
            current_task,
        )
        if repaired_graph_write_success is None:
            return PipelineTerminalDecision.abort_without_terminal()
        graph_write_success = repaired_graph_write_success

        retrieval_input = RetrievalIndexSyncInput(
            task_id=current_task.task_id,
            archive_id=current_task.archive_id,
            user_id=current_task.user_id,
            session_id=event.session_id,
            graph_write_success=graph_write_success,
            entity_alignment=alignment_success,
        )
        retrieval = await self._retrieval_index_sync_service.sync(
            retrieval_input,
            mongodb=self._mongodb,
            attempt_count=current_task.attempt_count,
        )
        if isinstance(retrieval, RetrievalIndexSyncAbort):
            return PipelineTerminalDecision.abort_without_terminal()
        if retrieval.outcome in (
            RetrievalIndexSyncOutcomeKind.SUCCESS,
            RetrievalIndexSyncOutcomeKind.SKIP_ALREADY_COMPLETED,
        ):
            return PipelineTerminalDecision.complete()
        if retrieval.failure is None:
            return PipelineTerminalDecision.abort_without_terminal()
        return PipelineTerminalDecision.fail(
            ExtractionLastError(
                error_code=retrieval.failure.error_code,
                failed_stage=retrieval.failure.failed_stage,
                message=retrieval.failure.message,
            )
        )

    async def _repair_empty_replay_index_sync_set(
        self,
        graph_write_success: GraphWriteSuccess,
        task: MemoryExtractionTask,
    ) -> GraphWriteSuccess | None:
        if graph_write_success.index_sync_memory_set:
            return graph_write_success
        loader = self._replay_index_sync_memory_set_loader
        if loader is None:
            return graph_write_success
        if task.extraction_result is None or not task.extraction_result.get("memories"):
            return graph_write_success
        try:
            index_sync_memory_set = await loader(task.user_id, task.archive_id)
        except Exception:
            return None
        if not index_sync_memory_set:
            return None
        return graph_write_success.model_copy(
            update={
                "index_sync_memory_set": index_sync_memory_set,
            }
        )

    @staticmethod
    def _alignment_failure_decision(
        outcome: EntityAlignmentOutcome,
    ) -> PipelineTerminalDecision:
        if outcome.failure is None:
            return PipelineTerminalDecision.abort_without_terminal()
        return PipelineTerminalDecision.fail(
            ExtractionLastError(
                error_code=outcome.failure.error_code,
                failed_stage=outcome.failure.failed_stage,
                message="entity alignment failed",
            )
        )

    @staticmethod
    def _reconciliation_failure_decision(
        outcome: ReconciliationOutcome,
    ) -> PipelineTerminalDecision:
        if outcome.failure is None:
            return PipelineTerminalDecision.abort_without_terminal()
        return PipelineTerminalDecision.fail(
            ExtractionLastError(
                error_code=outcome.failure.error_code.value,
                failed_stage=outcome.failure.failed_stage,
                message="reconciliation failed",
            )
        )

    @staticmethod
    def _graph_write_failure_decision(
        outcome: GraphWriteOutcome,
    ) -> PipelineTerminalDecision:
        if outcome.failure is None:
            return PipelineTerminalDecision.abort_without_terminal()
        return PipelineTerminalDecision.fail(
            ExtractionLastError(
                error_code=outcome.failure.error_code,
                failed_stage=outcome.failure.failed_stage,
                message="graph write failed",
            )
        )


def create_production_extraction_pipeline(
    mongodb: AsyncMongoClient[Any],
    neo4j_driver: Any,
    elasticsearch: Any,
    http_client: httpx.AsyncClient,
    settings: Settings,
    *,
    llm_client: LLMClient | None = None,
    tokenize_client: TokenizeClient | None = None,
    embedding_client: EmbeddingClient | None = None,
    clock: Clock | None = None,
    server_time_provider: Clock | None = None,
    before_retrieval_sync_hook: BeforeRetrievalSyncHook | None = None,
    replay_index_sync_memory_set_loader: ReplayIndexSyncMemorySetLoader | None = None,
) -> ProductionExtractionPipeline:
    """Build the production pipeline while allowing deterministic test clients."""
    resolved_llm_client = llm_client or DeepSeekLlmClient(settings)
    resolved_tokenize_client = tokenize_client or TeiTokenizeClient(settings, http_client)
    resolved_embedding_client = embedding_client or create_embedding_client(settings, http_client)
    resolved_server_time_provider = server_time_provider or clock
    resolved_replay_loader = replay_index_sync_memory_set_loader
    if resolved_replay_loader is None:

        async def resolved_replay_loader(
            user_id: str,
            archive_id: str,
        ) -> list[IndexSyncMemoryEntry]:
            return await _load_replay_index_sync_memory_set(
                neo4j_driver,
                resolved_tokenize_client,
                user_id=user_id,
                archive_id=archive_id,
            )

    extraction_llm_service = ExtractionLlmService(
        mongodb,
        resolved_llm_client,
        settings,
        clock=clock,
    )
    entity_alignment_service = create_entity_alignment_service(
        neo4j_driver,
        max_stored_entity_alias_count=settings.memory_extraction.max_stored_entity_alias_count,
    )
    reconciliation_service = create_reconciliation_service(
        neo4j_driver,
        llm_client=resolved_llm_client,
        settings=settings,
    )
    graph_write_service = create_graph_write_service(
        neo4j_driver,
        tokenize_client=resolved_tokenize_client,
        settings=settings,
        server_time_provider=resolved_server_time_provider,
    )
    retrieval_index_sync_service = create_retrieval_index_sync_service(
        neo4j_driver,
        elasticsearch,
        tokenize_client=resolved_tokenize_client,
        embedding_client=resolved_embedding_client,
        settings=settings,
        server_time_provider=resolved_server_time_provider,
    )
    return ProductionExtractionPipeline(
        mongodb,
        extraction_llm_service,
        entity_alignment_service,
        reconciliation_service,
        graph_write_service,
        retrieval_index_sync_service,
        before_retrieval_sync_hook=before_retrieval_sync_hook,
        replay_index_sync_memory_set_loader=resolved_replay_loader,
    )
