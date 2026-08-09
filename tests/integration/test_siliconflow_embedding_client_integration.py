"""Opt-in integration tests against real SiliconFlow embedding API."""

from __future__ import annotations

import os
from collections.abc import Iterator

import httpx
import pytest

from memory_system.infrastructure.embedding import (
    SiliconFlowEmbeddingClient,
    create_embedding_client,
)
from memory_system.settings import get_settings

INTEGRATION_ENV_FLAG = "RUN_SILICONFLOW_EMBEDDING_INTEGRATION"
INTEGRATION_API_KEY_ENV = "SILICONFLOW_API_KEY"


def _integration_enabled() -> bool:
    flag = os.environ.get(INTEGRATION_ENV_FLAG, "")
    api_key = os.environ.get(INTEGRATION_API_KEY_ENV, "")
    return flag == "1" and bool(api_key.strip())


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_siliconflow_single_and_batch_embeddings() -> None:
    if not _integration_enabled():
        pytest.skip(
            f"Set {INTEGRATION_ENV_FLAG}=1 and {INTEGRATION_API_KEY_ENV} to run integration tests"
        )

    settings = get_settings()
    async with httpx.AsyncClient() as http_client:
        client = create_embedding_client(settings, http_client)
        assert isinstance(client, SiliconFlowEmbeddingClient)

        single = await client.embed(["integration probe"])
        assert "bge-m3" in single.model
        assert len(single.vectors) == 1
        assert len(single.vectors[0]) == 1024

        batch = await client.embed(["batch-one", "batch-two", "batch-three"])
        assert len(batch.vectors) == 3
        for vector in batch.vectors:
            if len(vector) != 1024:
                pytest.fail(
                    "HALT: SiliconFlow BAAI/bge-m3 returned dimension != 1024; "
                    "do not change ES mapping without governance review"
                )
