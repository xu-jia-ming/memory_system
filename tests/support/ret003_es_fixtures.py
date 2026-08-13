"""RET-003 integration test Elasticsearch fixture helpers."""

from __future__ import annotations

from tests.support.ret002_es_fixtures import make_deterministic_embedding

from memory_system.domain.models.retrieval_index_sync import MemoryIndexDocument
from memory_system.infrastructure.elasticsearch.retrieval_index_write_repository import (
    RetrievalIndexWriteRepository,
)

USER_A = "user_ret003_a"
FIXED_NOW = 1_700_000_200
EMBEDDING_DIMENSION = 1024


def make_ret003_index_document(
    *,
    memory_id: str,
    user_id: str = USER_A,
    memory_type: str = "fact",
    status: str = "active",
    search_text: str = "ret003 fixture",
) -> MemoryIndexDocument:
    return MemoryIndexDocument(
        memory_id=memory_id,
        user_id=user_id,
        memory_type=memory_type,
        status=status,
        content=f"content-{memory_id}",
        search_text=search_text,
        predicate="works_on",
        event_status=None,
        latest_source_time=150,
        updated_time=FIXED_NOW,
        embedding=make_deterministic_embedding(memory_id),
    )


async def seed_ret003_es_documents(
    write_repo: RetrievalIndexWriteRepository,
    index_alias: str,
    *,
    memory_ids: list[str],
    user_id: str = USER_A,
) -> None:
    documents = [
        make_ret003_index_document(memory_id=memory_id, user_id=user_id) for memory_id in memory_ids
    ]
    await write_repo.bulk_upsert(index_alias, documents)
