"""RET-001 integration test Elasticsearch fixture helpers."""

from __future__ import annotations

from memory_system.domain.models.retrieval_index_sync import MemoryIndexDocument
from memory_system.infrastructure.elasticsearch.retrieval_index_write_repository import (
    RetrievalIndexWriteRepository,
)

RET001_KEYWORD = "ret001uniquekeyword"
USER_A = "user_ret001_a"
USER_B = "user_ret001_b"
FIXED_NOW = 1_700_000_000


def _dummy_embedding() -> list[float]:
    return [0.01] * 1024


def make_memory_index_document(
    *,
    memory_id: str,
    user_id: str,
    memory_type: str,
    status: str,
    search_text: str,
    content: str = "content",
    predicate: str = "works_on",
) -> MemoryIndexDocument:
    return MemoryIndexDocument(
        memory_id=memory_id,
        user_id=user_id,
        memory_type=memory_type,
        status=status,
        content=content,
        search_text=search_text,
        predicate=predicate,
        event_status=None,
        latest_source_time=150,
        updated_time=FIXED_NOW,
        embedding=_dummy_embedding(),
    )


async def seed_ret001_bm25_fixtures(
    write_repo: RetrievalIndexWriteRepository,
    index_alias: str,
    *,
    include_top_n_bulk: bool = False,
) -> dict[str, MemoryIndexDocument]:
    documents = [
        make_memory_index_document(
            memory_id="mem-a-active-fact",
            user_id=USER_A,
            memory_type="fact",
            status="active",
            search_text=f"{RET001_KEYWORD} fact active",
            content=f"{RET001_KEYWORD} fact content",
        ),
        make_memory_index_document(
            memory_id="mem-a-active-event",
            user_id=USER_A,
            memory_type="event",
            status="active",
            search_text=f"{RET001_KEYWORD} event active",
            content=f"{RET001_KEYWORD} event content",
        ),
        make_memory_index_document(
            memory_id="mem-a-conflicted-fact",
            user_id=USER_A,
            memory_type="fact",
            status="conflicted",
            search_text=f"{RET001_KEYWORD} conflicted fact",
            content=f"{RET001_KEYWORD} conflicted content",
        ),
        make_memory_index_document(
            memory_id="mem-a-superseded-fact",
            user_id=USER_A,
            memory_type="fact",
            status="superseded",
            search_text=f"{RET001_KEYWORD} superseded fact",
            content=f"{RET001_KEYWORD} superseded content",
        ),
        make_memory_index_document(
            memory_id="mem-a-active-profile",
            user_id=USER_A,
            memory_type="profile",
            status="active",
            search_text=f"{RET001_KEYWORD} profile active",
            content=f"{RET001_KEYWORD} profile content",
        ),
        make_memory_index_document(
            memory_id="mem-a-active-fact-nomatch",
            user_id=USER_A,
            memory_type="fact",
            status="active",
            search_text="unrelated text only",
            content="no keyword here",
        ),
        make_memory_index_document(
            memory_id="mem-b-active-fact",
            user_id=USER_B,
            memory_type="fact",
            status="active",
            search_text=f"{RET001_KEYWORD} user b fact",
            content=f"{RET001_KEYWORD} user b content",
        ),
    ]

    if include_top_n_bulk:
        for index in range(35):
            documents.append(
                make_memory_index_document(
                    memory_id=f"mem-a-bulk-{index:02d}",
                    user_id=USER_A,
                    memory_type="fact",
                    status="active",
                    search_text=f"{RET001_KEYWORD} bulk {index:02d}",
                    content=f"{RET001_KEYWORD} bulk content {index:02d}",
                )
            )

    await write_repo.bulk_upsert(index_alias, documents)
    return {document.memory_id: document for document in documents}
