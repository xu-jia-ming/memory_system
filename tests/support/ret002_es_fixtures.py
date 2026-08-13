"""RET-002 integration test Elasticsearch fixture helpers."""

from __future__ import annotations

import hashlib

from memory_system.domain.models.retrieval_index_sync import MemoryIndexDocument
from memory_system.infrastructure.elasticsearch.retrieval_index_write_repository import (
    RetrievalIndexWriteRepository,
)

RET002_KEYWORD = "ret002uniquekeyword"
RET002_SEMANTIC_QUERY = f"{RET002_KEYWORD} semantic anchor"
USER_A = "user_ret002_a"
USER_B = "user_ret002_b"
FIXED_NOW = 1_700_000_100
EMBEDDING_DIMENSION = 1024


def make_deterministic_embedding(key: str) -> list[float]:
    """Return a deterministic 1024-dim vector for the given key."""
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    vector: list[float] = []
    for index in range(EMBEDDING_DIMENSION):
        byte_value = digest[index % len(digest)]
        vector.append((byte_value / 127.5) - 1.0)
    return vector


def make_memory_index_document(
    *,
    memory_id: str,
    user_id: str,
    memory_type: str,
    status: str,
    search_text: str,
    embedding_key: str,
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
        embedding=make_deterministic_embedding(embedding_key),
    )


async def seed_ret002_hybrid_fixtures(
    write_repo: RetrievalIndexWriteRepository,
    index_alias: str,
    *,
    include_fused_top_n_bulk: bool = False,
) -> dict[str, MemoryIndexDocument]:
    semantic_key = RET002_SEMANTIC_QUERY
    documents = [
        make_memory_index_document(
            memory_id="mem-a-close-vector",
            user_id=USER_A,
            memory_type="fact",
            status="active",
            search_text=f"{RET002_KEYWORD} close vector fact",
            embedding_key=semantic_key,
        ),
        make_memory_index_document(
            memory_id="mem-a-far-vector",
            user_id=USER_A,
            memory_type="fact",
            status="active",
            search_text=f"{RET002_KEYWORD} far vector fact",
            embedding_key="ret002-far-embedding",
        ),
        make_memory_index_document(
            memory_id="mem-a-vector-only",
            user_id=USER_A,
            memory_type="event",
            status="active",
            search_text="unrelated semantic only",
            embedding_key=semantic_key,
        ),
        make_memory_index_document(
            memory_id="mem-a-conflicted-fact",
            user_id=USER_A,
            memory_type="fact",
            status="conflicted",
            search_text=f"{RET002_KEYWORD} conflicted fact",
            embedding_key="ret002-conflicted",
        ),
        make_memory_index_document(
            memory_id="mem-a-superseded-fact",
            user_id=USER_A,
            memory_type="fact",
            status="superseded",
            search_text=f"{RET002_KEYWORD} superseded fact",
            embedding_key="ret002-superseded",
        ),
        make_memory_index_document(
            memory_id="mem-b-active-fact",
            user_id=USER_B,
            memory_type="fact",
            status="active",
            search_text=f"{RET002_KEYWORD} user b fact",
            embedding_key=semantic_key,
        ),
    ]

    if include_fused_top_n_bulk:
        for index in range(35):
            documents.append(
                make_memory_index_document(
                    memory_id=f"mem-a-bulk-{index:02d}",
                    user_id=USER_A,
                    memory_type="fact",
                    status="active",
                    search_text=f"{RET002_KEYWORD} bulk {index:02d}",
                    embedding_key=f"ret002-bulk-{index:02d}",
                )
            )

    await write_repo.bulk_upsert(index_alias, documents)
    return {document.memory_id: document for document in documents}
