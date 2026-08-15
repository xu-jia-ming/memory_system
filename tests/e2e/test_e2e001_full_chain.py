"""E2E-001 happy-path full chain: Session → Close through Extraction/Retrieval/Consolidation."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
import redis.asyncio as aioredis
from pymongo import AsyncMongoClient

from memory_system.domain.enums.working_memory import SessionStatus
from memory_system.settings import get_settings
from tests.e2e.conftest import Ext009Runtime, InfraStack
from tests.e2e.helpers.con005_e2e_helpers import assert_run_success
from tests.e2e.helpers.e2e001_helpers import (
    E2E001_EVALUATION_TIME,
    KEYWORD,
    assert_redis_wm_gone,
    assert_request_id_echo,
    build_consolidation_run_service,
    build_e2e001_app_client,
    cleanup_e2e001_data,
    create_session_via_http,
    drive_compression_succeeded,
    read_memory_version_and_consolidated,
    run_extraction_for_archive,
)
from tests.e2e.helpers.ext009_e2e_helpers import (
    count_user_graph_nodes,
    count_user_index_documents,
    graph_memory_ids,
)
from tests.e2e.helpers.ret006_e2e_helpers import (
    assert_retrieval_response_contract,
    post_retrieval,
)
from tests.e2e.helpers.stm_e2e_helpers import (
    consume_kafka_events,
    list_archives_for_session,
    new_test_ids,
    post_close,
    read_wm_meta,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_hp_session_to_close_full_chain(
    infra_stack: InfraStack,
    redis_client: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    ext009_runtime: Ext009Runtime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, _ = new_test_ids("e2e001hp")
    other_user_id, _ = new_test_ids("e2e001iso")
    session_request_id = str(uuid.uuid4())
    retrieval_request_id = str(uuid.uuid4())
    close_request_id = str(uuid.uuid4())
    session_id = ""

    async with build_e2e001_app_client(infra_stack, monkeypatch) as runtime:
        try:
            assert get_settings().embedding_effective_runtime_mode == "cpu"

            session_id = await create_session_via_http(
                runtime.http_client,
                user_id=user_id,
                request_id=session_request_id,
            )
            meta_created = await read_wm_meta(redis_client, user_id, session_id)
            assert meta_created is not None
            assert meta_created.status == SessionStatus.ACTIVE

            _trigger_resp, archives = await drive_compression_succeeded(
                runtime.http_client,
                redis_client,
                mongo_client,
                user_id=user_id,
                session_id=session_id,
            )
            compression_archive = next(
                archive for archive in archives if archive.base_compression_version == 0
            )
            kafka_events = await consume_kafka_events(
                infra_stack.kafka_bootstrap,
                user_id=user_id,
                session_id=session_id,
                archive_id=compression_archive.archive_id,
                group_id=f"e2e001-hp-kafka-{uuid.uuid4().hex[:8]}",
            )
            assert kafka_events, "Kafka context.archive.created missing after compression"

            _, _, _, _ = await run_extraction_for_archive(
                mongodb=mongo_client,
                infra_stack=infra_stack,
                ext009_runtime=ext009_runtime,
                archive=compression_archive,
                group_id=f"e2e001-hp-worker-{uuid.uuid4().hex[:8]}",
            )
            memory_ids = await graph_memory_ids(ext009_runtime.neo4j_driver, user_id)
            assert len(memory_ids) == 1
            memory_id = next(iter(memory_ids))
            assert await count_user_graph_nodes(
                ext009_runtime.neo4j_driver, "Evidence", user_id
            ) >= 1
            assert await ext009_runtime.elasticsearch.exists(
                index=ext009_runtime.settings.memory_retrieval.index_name,
                id=memory_id,
            )
            assert (
                await count_user_index_documents(
                    ext009_runtime.elasticsearch,
                    index_name=ext009_runtime.settings.memory_retrieval.index_name,
                    user_id=user_id,
                )
                == 1
            )

            retrieval_resp = await post_retrieval(
                runtime.http_client,
                user_id=user_id,
                query=KEYWORD,
                request_id=retrieval_request_id,
            )
            assert retrieval_resp.status_code == 200, retrieval_resp.text
            assert_request_id_echo(retrieval_resp, retrieval_request_id)
            retrieval_body = retrieval_resp.json()
            assert_retrieval_response_contract(retrieval_body)
            returned_ids = {item["memory_id"] for item in retrieval_body["memories"]}
            assert memory_id in returned_ids

            isolation_resp = await post_retrieval(
                runtime.http_client,
                user_id=other_user_id,
                query=KEYWORD,
                request_id=str(uuid.uuid4()),
            )
            assert isolation_resp.status_code == 200, isolation_resp.text
            isolation_ids = {
                item["memory_id"] for item in isolation_resp.json().get("memories", [])
            }
            assert memory_id not in isolation_ids

            before_cons_time, before_version = await read_memory_version_and_consolidated(
                ext009_runtime,
                user_id=user_id,
                memory_id=memory_id,
            )
            run_service = build_consolidation_run_service(ext009_runtime)
            result = await run_service.execute_run(E2E001_EVALUATION_TIME)
            assert_run_success(result)
            after_cons_time, after_version = await read_memory_version_and_consolidated(
                ext009_runtime,
                user_id=user_id,
                memory_id=memory_id,
            )
            assert after_cons_time == E2E001_EVALUATION_TIME
            assert after_cons_time != before_cons_time
            assert after_version == before_version

            archive_count_before_close = len(
                await list_archives_for_session(mongo_client, session_id)
            )
            close_resp = await post_close(
                runtime.http_client,
                user_id=user_id,
                session_id=session_id,
                request_id=close_request_id,
            )
            assert close_resp.status_code == 200, close_resp.text
            assert_request_id_echo(close_resp, close_request_id)
            close_body = close_resp.json()
            assert close_body["status"] == "closed"
            assert close_body["archive_ids"]
            await assert_redis_wm_gone(redis_client, user_id, session_id)
            archives_after_close = await list_archives_for_session(mongo_client, session_id)
            assert len(archives_after_close) >= archive_count_before_close
            assert any(
                archive.archive_id in set(close_body["archive_ids"])
                or archive.base_compression_version >= 1
                for archive in archives_after_close
            )
        finally:
            await cleanup_e2e001_data(
                redis_client,
                mongo_client,
                ext009_runtime,
                user_id=user_id,
                session_id=session_id or "missing",
                extra_user_ids=[other_user_id],
            )
