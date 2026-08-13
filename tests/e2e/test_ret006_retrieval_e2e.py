"""RET-006 retrieval stage E2E with failure injection."""

from __future__ import annotations

import time
import uuid

import httpx
import pytest

from memory_system.infrastructure.tei.fake_tokenize_client import FakeTokenizeClient
from tests.e2e.conftest import InfraStack
from tests.e2e.helpers.ret006_e2e_helpers import (
    FATAL_TIMEOUT_ENV,
    MEMORY_A_PRIMARY,
    MEMORY_B_ISOLATION,
    RET006_SEMANTIC_QUERY,
    TIGHT_TIMEOUT_ENV,
    USER_RET006_A,
    USER_RET006_B,
    Ret006AlignedEmbeddingClient,
    assert_retrieval_response_contract,
    build_channel_failure_overrides,
    build_retrieval_client,
    cleanup_ret006_data,
    post_retrieval,
    read_memory_stats,
    seed_ret006_aligned,
    seed_ret006_ext007_synced,
)
from tests.support.fake_retrieval_index_embedding_client import FakeEmbeddingClient

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_e2e1_happy_path_hybrid_retrieval(
    infra_stack: InfraStack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_id = str(uuid.uuid4())
    async with build_retrieval_client(
        infra_stack,
        monkeypatch,
        embedding=Ret006AlignedEmbeddingClient(),
        tokenize=FakeTokenizeClient(token_count=10),
        request_id=request_id,
    ) as runtime:
        await seed_ret006_aligned(runtime)
        baseline = await read_memory_stats(
            runtime.neo4j_driver,
            user_id=USER_RET006_A,
            memory_id=MEMORY_A_PRIMARY,
        )
        assert baseline is not None
        assert baseline.retrieval_count == 0
        try:
            before = int(time.time())
            response = await post_retrieval(
                runtime.http_client,
                user_id=USER_RET006_A,
                query=RET006_SEMANTIC_QUERY,
                request_id=request_id,
            )
            after = int(time.time())
            assert response.status_code == 200
            body = response.json()
            assert_retrieval_response_contract(body)
            assert body["retrieval_mode"] == "hybrid"
            memory_ids = [item["memory_id"] for item in body["memories"]]
            assert MEMORY_A_PRIMARY in memory_ids
            matched = next(
                item for item in body["memories"] if item["memory_id"] == MEMORY_A_PRIMARY
            )
            assert matched["evidence_count"] >= 1
            assert matched["source_message_ids"]
            assert response.headers.get("X-Request-ID") == request_id

            stats = await read_memory_stats(
                runtime.neo4j_driver,
                user_id=USER_RET006_A,
                memory_id=MEMORY_A_PRIMARY,
            )
            assert stats is not None
            assert stats.retrieval_count == baseline.retrieval_count + 1
            assert stats.last_retrieved_time is not None
            assert before - 5 <= stats.last_retrieved_time <= after + 5
        finally:
            await cleanup_ret006_data(
                runtime,
                user_ids=[USER_RET006_A, USER_RET006_B],
            )


@pytest.mark.asyncio
async def test_e2e2_ext007_write_to_retrieve(
    infra_stack: InfraStack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with build_retrieval_client(
        infra_stack,
        monkeypatch,
        embedding=FakeEmbeddingClient(),
        tokenize=FakeTokenizeClient(token_count=10),
    ) as runtime:
        seeded = await seed_ret006_ext007_synced(runtime)
        user_id = seeded["user_id"]
        memory_id = seeded["memory_id"]
        content = seeded["content"]
        archive_id = seeded["archive_id"]
        try:
            response = await post_retrieval(
                runtime.http_client,
                user_id=user_id,
                query=content,
            )
            assert response.status_code == 200
            body = response.json()
            assert body["retrieval_mode"] in {"hybrid", "bm25_only", "vector_only"}
            memory_ids = [item["memory_id"] for item in body["memories"]]
            assert memory_id in memory_ids
            matched = next(item for item in body["memories"] if item["memory_id"] == memory_id)
            assert matched["content"] == content
        finally:
            await cleanup_ret006_data(
                runtime,
                user_ids=[user_id],
                archive_ids=[archive_id],
            )


@pytest.mark.asyncio
async def test_e2e3_embedding_unavailable_degradation(
    infra_stack: InfraStack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with build_retrieval_client(
        infra_stack,
        monkeypatch,
        embedding=Ret006AlignedEmbeddingClient(fail=True),
        tokenize=FakeTokenizeClient(token_count=10),
    ) as runtime:
        await seed_ret006_aligned(runtime)
        baseline = await read_memory_stats(
            runtime.neo4j_driver,
            user_id=USER_RET006_A,
            memory_id=MEMORY_A_PRIMARY,
        )
        assert baseline is not None
        try:
            response = await post_retrieval(
                runtime.http_client,
                user_id=USER_RET006_A,
                query=RET006_SEMANTIC_QUERY,
            )
            assert response.status_code == 200
            body = response.json()
            assert body["retrieval_mode"] == "bm25_only"
            assert "embedding_failed" in body["warnings"]
            assert any(item["memory_id"] == MEMORY_A_PRIMARY for item in body["memories"])

            stats = await read_memory_stats(
                runtime.neo4j_driver,
                user_id=USER_RET006_A,
                memory_id=MEMORY_A_PRIMARY,
            )
            assert stats is not None
            assert stats.retrieval_count == baseline.retrieval_count + 1
        finally:
            await cleanup_ret006_data(
                runtime,
                user_ids=[USER_RET006_A, USER_RET006_B],
            )


@pytest.mark.asyncio
async def test_e2e4a_single_channel_bm25_degradation(
    infra_stack: InfraStack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with build_retrieval_client(
        infra_stack,
        monkeypatch,
        embedding=Ret006AlignedEmbeddingClient(),
        tokenize=FakeTokenizeClient(token_count=10),
        service_overrides=build_channel_failure_overrides(bm25=True),
    ) as runtime:
        await seed_ret006_aligned(runtime)
        baseline = await read_memory_stats(
            runtime.neo4j_driver,
            user_id=USER_RET006_A,
            memory_id=MEMORY_A_PRIMARY,
        )
        assert baseline is not None
        try:
            response = await post_retrieval(
                runtime.http_client,
                user_id=USER_RET006_A,
                query=RET006_SEMANTIC_QUERY,
            )
            assert response.status_code == 200
            body = response.json()
            assert "bm25_retrieval_failed" in body["warnings"]
            assert body["retrieval_mode"] in {"vector_only", "hybrid"}
            assert any(item["memory_id"] == MEMORY_A_PRIMARY for item in body["memories"])

            stats = await read_memory_stats(
                runtime.neo4j_driver,
                user_id=USER_RET006_A,
                memory_id=MEMORY_A_PRIMARY,
            )
            assert stats is not None
            assert stats.retrieval_count == baseline.retrieval_count + 1
        finally:
            await cleanup_ret006_data(
                runtime,
                user_ids=[USER_RET006_A, USER_RET006_B],
            )


@pytest.mark.asyncio
async def test_e2e4b_dual_channel_fatal_unavailable(
    infra_stack: InfraStack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with build_retrieval_client(
        infra_stack,
        monkeypatch,
        embedding=Ret006AlignedEmbeddingClient(),
        tokenize=FakeTokenizeClient(token_count=10),
        service_overrides=build_channel_failure_overrides(bm25=True, vector=True),
    ) as runtime:
        await seed_ret006_aligned(runtime)
        baseline_a = await read_memory_stats(
            runtime.neo4j_driver,
            user_id=USER_RET006_A,
            memory_id=MEMORY_A_PRIMARY,
        )
        assert baseline_a is not None
        try:
            response = await post_retrieval(
                runtime.http_client,
                user_id=USER_RET006_A,
                query=RET006_SEMANTIC_QUERY,
            )
            assert response.status_code == 503
            body = response.json()
            assert body["error"]["code"] == "retrieval_unavailable"
            assert "message" in body["error"]
            assert "warnings" not in body
            assert "retrieval_mode" not in body
            assert "memories" not in body

            stats = await read_memory_stats(
                runtime.neo4j_driver,
                user_id=USER_RET006_A,
                memory_id=MEMORY_A_PRIMARY,
            )
            assert stats is not None
            assert stats.retrieval_count == baseline_a.retrieval_count
            assert stats.last_retrieved_time == baseline_a.last_retrieved_time
        finally:
            await cleanup_ret006_data(
                runtime,
                user_ids=[USER_RET006_A, USER_RET006_B],
            )


@pytest.mark.asyncio
async def test_e2e5a_total_timeout_before_response(
    infra_stack: InfraStack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with build_retrieval_client(
        infra_stack,
        monkeypatch,
        embedding=Ret006AlignedEmbeddingClient(),
        tokenize=FakeTokenizeClient(token_count=10),
        scoring_delay_seconds=3.0,
        extra_env=FATAL_TIMEOUT_ENV,
    ) as runtime:
        await seed_ret006_aligned(runtime)
        baseline = await read_memory_stats(
            runtime.neo4j_driver,
            user_id=USER_RET006_A,
            memory_id=MEMORY_A_PRIMARY,
        )
        assert baseline is not None
        try:
            response = await post_retrieval(
                runtime.http_client,
                user_id=USER_RET006_A,
                query=RET006_SEMANTIC_QUERY,
            )
            assert response.status_code == 503
            body = response.json()
            assert body["error"]["code"] == "retrieval_timeout"

            stats = await read_memory_stats(
                runtime.neo4j_driver,
                user_id=USER_RET006_A,
                memory_id=MEMORY_A_PRIMARY,
            )
            assert stats is not None
            assert stats.retrieval_count == baseline.retrieval_count
        finally:
            await cleanup_ret006_data(
                runtime,
                user_ids=[USER_RET006_A, USER_RET006_B],
            )


@pytest.mark.asyncio
async def test_e2e5b_total_timeout_degraded_after_response(
    infra_stack: InfraStack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with build_retrieval_client(
        infra_stack,
        monkeypatch,
        embedding=Ret006AlignedEmbeddingClient(),
        tokenize=FakeTokenizeClient(token_count=10),
        stats_delay_seconds=3.0,
        extra_env=TIGHT_TIMEOUT_ENV,
    ) as runtime:
        await seed_ret006_aligned(runtime)
        baseline = await read_memory_stats(
            runtime.neo4j_driver,
            user_id=USER_RET006_A,
            memory_id=MEMORY_A_PRIMARY,
        )
        assert baseline is not None
        try:
            response = await post_retrieval(
                runtime.http_client,
                user_id=USER_RET006_A,
                query=RET006_SEMANTIC_QUERY,
            )
            assert response.status_code == 200
            body = response.json()
            assert "retrieval_timeout_degraded" in body["warnings"]
            assert body["memories"]

            stats = await read_memory_stats(
                runtime.neo4j_driver,
                user_id=USER_RET006_A,
                memory_id=MEMORY_A_PRIMARY,
            )
            assert stats is not None
            assert stats.retrieval_count == baseline.retrieval_count
        finally:
            await cleanup_ret006_data(
                runtime,
                user_ids=[USER_RET006_A, USER_RET006_B],
            )


@pytest.mark.asyncio
async def test_e2e6_user_isolation_and_stats(
    infra_stack: InfraStack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with build_retrieval_client(
        infra_stack,
        monkeypatch,
        embedding=Ret006AlignedEmbeddingClient(),
        tokenize=FakeTokenizeClient(token_count=10),
    ) as runtime:
        await seed_ret006_aligned(runtime)
        baseline_a = await read_memory_stats(
            runtime.neo4j_driver,
            user_id=USER_RET006_A,
            memory_id=MEMORY_A_PRIMARY,
        )
        baseline_b = await read_memory_stats(
            runtime.neo4j_driver,
            user_id=USER_RET006_B,
            memory_id=MEMORY_B_ISOLATION,
        )
        assert baseline_a is not None
        assert baseline_b is not None
        try:
            response = await post_retrieval(
                runtime.http_client,
                user_id=USER_RET006_A,
                query=RET006_SEMANTIC_QUERY,
            )
            assert response.status_code == 200
            body = response.json()
            memory_ids = [item["memory_id"] for item in body["memories"]]
            assert MEMORY_B_ISOLATION not in memory_ids

            stats_a = await read_memory_stats(
                runtime.neo4j_driver,
                user_id=USER_RET006_A,
                memory_id=MEMORY_A_PRIMARY,
            )
            stats_b = await read_memory_stats(
                runtime.neo4j_driver,
                user_id=USER_RET006_B,
                memory_id=MEMORY_B_ISOLATION,
            )
            assert stats_a is not None
            assert stats_b is not None
            assert stats_a.retrieval_count == baseline_a.retrieval_count + 1
            assert stats_b.retrieval_count == baseline_b.retrieval_count
            assert stats_b.last_retrieved_time == baseline_b.last_retrieved_time
        finally:
            await cleanup_ret006_data(
                runtime,
                user_ids=[USER_RET006_A, USER_RET006_B],
            )


@pytest.mark.asyncio
async def test_auth_invalid_api_key(
    ret006_retrieval_client: httpx.AsyncClient,
) -> None:
    response = await ret006_retrieval_client.post(
        "/api/v1/memory/retrieval",
        headers={"X-API-Key": "invalid-key"},
        json={"user_id": USER_RET006_A, "query": "hello"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"
