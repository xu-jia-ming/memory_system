"""EXT-007 retrieval index sync orchestration service."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Protocol

import structlog
from prometheus_client import Counter
from pymongo import AsyncMongoClient

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.domain.models.extraction_task import ExtractionLastError
from memory_system.domain.models.graph_write import IndexSyncMemoryEntry
from memory_system.domain.models.retrieval_index_sync import (
    MemoryIndexDocument,
    MemoryIndexRow,
    RetrievalIndexSyncAbort,
    RetrievalIndexSyncFailure,
    RetrievalIndexSyncInput,
    RetrievalIndexSyncOutcome,
    RetrievalIndexSyncOutcomeKind,
    RetrievalIndexSyncSkip,
    RetrievalIndexSyncSuccess,
)
from memory_system.domain.ports.tokenize_client import TokenizeClient
from memory_system.domain.services.core_search_text import build_core_search_text
from memory_system.domain.services.entity_key import build_user_entity_id
from memory_system.domain.services.index_sync_set_expander import (
    expand_index_sync_memory_ids,
    extract_non_user_aligned_entity_ids,
)
from memory_system.domain.services.search_text_builder import build_search_text_with_alias_budget
from memory_system.infrastructure.elasticsearch.retrieval_index_write_repository import (
    RetrievalIndexWriteError,
)
from memory_system.infrastructure.embedding.errors import EmbeddingServiceError
from memory_system.infrastructure.embedding.types import EmbeddingClient
from memory_system.infrastructure.mongodb import extraction_task_repository as task_repo
from memory_system.infrastructure.tei.tei_tokenize_client import TokenizeServiceError
from memory_system.settings.models import Settings

_logger = structlog.get_logger(__name__)

EMBEDDING_BATCH_SIZE = 32

MEMORY_SEARCH_TEXT_OMITTED_ALIAS_TOTAL = Counter(
    "memory_search_text_omitted_alias_total",
    "Aliases omitted from search_text due to token budget",
)

ServerTimeProvider = Callable[[], int]


class RetrievalIndexReadPort(Protocol):
    async def expand_related_memory_ids(
        self, user_id: str, seed_memory_ids: set[str]
    ) -> set[str]: ...

    async def expand_entity_linked_memory_ids(
        self, user_id: str, entity_ids: list[str]
    ) -> set[str]: ...

    async def load_memory_index_rows(
        self, user_id: str, memory_ids: set[str]
    ) -> list[MemoryIndexRow]: ...


class RetrievalIndexWritePort(Protocol):
    async def bulk_upsert(
        self, index_alias: str, documents: list[MemoryIndexDocument]
    ) -> None: ...


class RetrievalIndexSyncService:
    """Library service for retrieval index document sync (EXT-007)."""

    def __init__(
        self,
        read_repository: RetrievalIndexReadPort,
        write_repository: RetrievalIndexWritePort,
        *,
        tokenize_client: TokenizeClient,
        embedding_client: EmbeddingClient,
        settings: Settings,
        server_time_provider: ServerTimeProvider | None = None,
    ) -> None:
        self._read_repository = read_repository
        self._write_repository = write_repository
        self._tokenize_client = tokenize_client
        self._embedding_client = embedding_client
        self._settings = settings
        self._server_time_provider = server_time_provider or (lambda: int(time.time()))

    async def sync(
        self,
        sync_input: RetrievalIndexSyncInput,
        *,
        mongodb: AsyncMongoClient[Any],
        attempt_count: int | None = None,
    ) -> RetrievalIndexSyncOutcome | RetrievalIndexSyncAbort:
        precondition_abort = self._validate_preconditions(sync_input)
        if precondition_abort is not None:
            return precondition_abort

        task = await task_repo.find_extraction_task_by_archive_id(
            mongodb,
            sync_input.archive_id,
        )
        if task is None:
            return RetrievalIndexSyncAbort()
        if task.user_id != sync_input.user_id:
            return RetrievalIndexSyncAbort()
        if task.status == ExtractionTaskStatus.COMPLETED:
            return RetrievalIndexSyncOutcome(
                outcome=RetrievalIndexSyncOutcomeKind.SKIP_ALREADY_COMPLETED,
                skip=RetrievalIndexSyncSkip(task=task),
            )
        if task.status != ExtractionTaskStatus.PROCESSING:
            return RetrievalIndexSyncAbort()

        attempt = attempt_count if attempt_count is not None else task.attempt_count

        try:
            return await self._sync_processing_task(
                sync_input,
                mongodb=mongodb,
                attempt_count=attempt,
            )
        except (
            RetrievalIndexWriteError,
            EmbeddingServiceError,
            TokenizeServiceError,
            RuntimeError,
        ) as exc:
            return await self._fail_task(
                sync_input,
                mongodb=mongodb,
                message=self._sanitize_failure_message(exc),
                attempt_count=attempt,
            )
        except Exception as exc:
            return await self._fail_task(
                sync_input,
                mongodb=mongodb,
                message=self._sanitize_failure_message(exc),
                attempt_count=attempt,
            )

    async def _sync_processing_task(
        self,
        sync_input: RetrievalIndexSyncInput,
        *,
        mongodb: AsyncMongoClient[Any],
        attempt_count: int,
    ) -> RetrievalIndexSyncOutcome | RetrievalIndexSyncAbort:
        seed_ids = {
            entry.memory_id for entry in sync_input.graph_write_success.index_sync_memory_set
        }
        handoff_by_memory_id = {
            entry.memory_id: entry
            for entry in sync_input.graph_write_success.index_sync_memory_set
        }

        related_ids = await self._read_repository.expand_related_memory_ids(
            sync_input.user_id,
            seed_ids,
        )
        entity_ids = extract_non_user_aligned_entity_ids(
            sync_input.entity_alignment,
            sync_input.user_id,
        )
        entity_linked_ids = await self._read_repository.expand_entity_linked_memory_ids(
            sync_input.user_id,
            entity_ids,
        )
        memory_ids = expand_index_sync_memory_ids(
            seed_memory_ids=seed_ids,
            related_memory_ids=related_ids,
            entity_linked_memory_ids=entity_linked_ids,
        )

        if not memory_ids:
            completed = await task_repo.mark_completed(
                mongodb,
                archive_id=sync_input.archive_id,
                now=self._server_time_provider(),
            )
            return RetrievalIndexSyncOutcome(
                outcome=RetrievalIndexSyncOutcomeKind.SUCCESS,
                success=RetrievalIndexSyncSuccess(
                    user_id=sync_input.user_id,
                    archive_id=sync_input.archive_id,
                    synced_memory_count=0,
                    omitted_alias_total=0,
                    task=completed,
                ),
            )

        rows = await self._read_repository.load_memory_index_rows(sync_input.user_id, memory_ids)
        loaded_ids = {row.memory_id for row in rows}
        if loaded_ids != memory_ids:
            raise RuntimeError("neo4j memory rows missing for expanded index sync set")

        documents, omitted_alias_total = await self._build_documents(
            sync_input.user_id,
            rows,
            handoff_by_memory_id,
        )
        if omitted_alias_total:
            MEMORY_SEARCH_TEXT_OMITTED_ALIAS_TOTAL.inc(omitted_alias_total)

        await self._write_repository.bulk_upsert(
            self._settings.memory_retrieval.index_name,
            documents,
        )

        completed = await task_repo.mark_completed(
            mongodb,
            archive_id=sync_input.archive_id,
            now=self._server_time_provider(),
        )
        return RetrievalIndexSyncOutcome(
            outcome=RetrievalIndexSyncOutcomeKind.SUCCESS,
            success=RetrievalIndexSyncSuccess(
                user_id=sync_input.user_id,
                archive_id=sync_input.archive_id,
                synced_memory_count=len(documents),
                omitted_alias_total=omitted_alias_total,
                task=completed,
            ),
        )

    async def _build_documents(
        self,
        user_id: str,
        rows: list[MemoryIndexRow],
        handoff_by_memory_id: dict[str, IndexSyncMemoryEntry],
    ) -> tuple[list[MemoryIndexDocument], int]:
        user_entity_id = build_user_entity_id(user_id)
        max_tokens = self._settings.memory_extraction.max_search_text_tokens

        search_texts: list[str] = []
        row_order: list[MemoryIndexRow] = []
        omitted_alias_total = 0

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
            handoff = handoff_by_memory_id.get(row.memory_id)
            core_token_count: int | None = None
            if handoff is not None and handoff.core_search_text == core_search_text:
                core_search_text = handoff.core_search_text
                core_token_count = handoff.token_count

            subject_aliases = (
                []
                if row.subject_entity_id == user_entity_id
                else list(row.subject_aliases)
            )
            object_aliases: list[str] = []
            if row.object_entity_id is not None and row.object_entity_id != user_entity_id:
                object_aliases = list(row.object_aliases)

            build_result = await build_search_text_with_alias_budget(
                core_search_text=core_search_text,
                subject_aliases=subject_aliases,
                object_aliases=object_aliases,
                user_id=user_id,
                subject_entity_id=row.subject_entity_id,
                object_entity_id=row.object_entity_id,
                tokenize_client=self._tokenize_client,
                max_tokens=max_tokens,
                core_token_count=core_token_count,
            )
            omitted_alias_total += build_result.omitted_alias_count
            search_texts.append(build_result.search_text)
            row_order.append(row)

        vectors = await self._embed_in_batches(search_texts)
        documents = [
            MemoryIndexDocument(
                memory_id=row.memory_id,
                user_id=row.user_id,
                memory_type=row.memory_type,
                status=row.status,
                content=row.content,
                search_text=search_text,
                predicate=row.predicate,
                event_status=row.event_status,
                latest_source_time=row.latest_source_time,
                updated_time=row.updated_time,
                embedding=vector,
            )
            for row, search_text, vector in zip(row_order, search_texts, vectors, strict=True)
        ]
        return documents, omitted_alias_total

    async def _embed_in_batches(self, search_texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(search_texts), EMBEDDING_BATCH_SIZE):
            batch = search_texts[start : start + EMBEDDING_BATCH_SIZE]
            result = await self._embedding_client.embed(batch)
            if len(result.vectors) != len(batch):
                raise RuntimeError("embedding batch size mismatch")
            vectors.extend(result.vectors)
        return vectors

    async def _fail_task(
        self,
        sync_input: RetrievalIndexSyncInput,
        *,
        mongodb: AsyncMongoClient[Any],
        message: str,
        attempt_count: int,
    ) -> RetrievalIndexSyncOutcome | RetrievalIndexSyncAbort:
        last_error = ExtractionLastError(
            error_code="retrieval_index_write_failed",
            failed_stage="retrieval_index",
            message=message,
        )
        try:
            failed_task = await task_repo.mark_failed(
                mongodb,
                archive_id=sync_input.archive_id,
                last_error=last_error,
                now=self._server_time_provider(),
            )
        except RuntimeError:
            return RetrievalIndexSyncAbort()

        self._log_failure(sync_input, attempt_count=attempt_count)
        return RetrievalIndexSyncOutcome(
            outcome=RetrievalIndexSyncOutcomeKind.FAILURE,
            failure=RetrievalIndexSyncFailure(message=message, task=failed_task),
        )

    def _validate_preconditions(
        self,
        sync_input: RetrievalIndexSyncInput,
    ) -> RetrievalIndexSyncAbort | None:
        if sync_input.graph_write_success.user_id != sync_input.user_id:
            return RetrievalIndexSyncAbort()
        if sync_input.graph_write_success.archive_id != sync_input.archive_id:
            return RetrievalIndexSyncAbort()
        if sync_input.entity_alignment.user_id != sync_input.user_id:
            return RetrievalIndexSyncAbort()
        return None

    def _sanitize_failure_message(self, exc: Exception) -> str:
        return type(exc).__name__

    def _log_failure(
        self,
        sync_input: RetrievalIndexSyncInput,
        *,
        attempt_count: int,
    ) -> None:
        log_kwargs: dict[str, str | int] = {
            "task_id": sync_input.task_id,
            "archive_id": sync_input.archive_id,
            "user_id": sync_input.user_id,
            "failed_stage": "retrieval_index",
            "error_code": "retrieval_index_write_failed",
            "attempt_count": attempt_count,
        }
        if sync_input.session_id is not None:
            log_kwargs["session_id"] = sync_input.session_id
        _logger.warning("retrieval index sync failed", **log_kwargs)


def create_retrieval_index_sync_service(
    driver: Any,
    elasticsearch: Any,
    *,
    tokenize_client: TokenizeClient,
    embedding_client: EmbeddingClient,
    settings: Settings,
    server_time_provider: ServerTimeProvider | None = None,
) -> RetrievalIndexSyncService:
    from memory_system.infrastructure.elasticsearch.retrieval_index_write_repository import (
        RetrievalIndexWriteRepository,
    )
    from memory_system.infrastructure.neo4j.retrieval_index_read_repository import (
        RetrievalIndexReadRepository,
    )

    return RetrievalIndexSyncService(
        RetrievalIndexReadRepository(driver),
        RetrievalIndexWriteRepository(elasticsearch),
        tokenize_client=tokenize_client,
        embedding_client=embedding_client,
        settings=settings,
        server_time_provider=server_time_provider,
    )
