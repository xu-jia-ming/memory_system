"""Unit tests for compression finalize domain service orchestration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from memory_system.domain.enums.compression_finalize import CompressionFinalizeStatus
from memory_system.domain.models.compression_finalize import CompressionFinalizeInput
from memory_system.domain.models.compression_llm import CompressionFinalizeLlmPayload
from memory_system.domain.services.compression_finalize_service import (
    CompressionFinalizeValidationError,
    finalize_compression,
)
from memory_system.infrastructure.redis.compression_finalize_repository import (
    CompressionFinalizeLuaOutcome,
)

USER_ID = "user_001"
SESSION_ID = "session_001"
ARCHIVE_ID = "arch-001"
BATCH_KEY = "session_001:m1:m2"
LOCK_TOKEN = "lock-token-001"
FIXED_NOW = 1_700_000_000


def _input(**overrides: object) -> CompressionFinalizeInput:
    data: dict[str, object] = {
        "user_id": USER_ID,
        "session_id": SESSION_ID,
        "expected_compression_version": 0,
        "pending_archive_id": ARCHIVE_ID,
        "pending_archive_batch_key": BATCH_KEY,
        "pending_archive_message_count": 2,
        "pending_archive_estimated_tokens": 300,
        "expected_first_message_id": "m1",
        "expected_last_message_id": "m2",
        "archived_message_tokens": 300,
        "old_compressed_context_tokens": 50,
        "lock_owner_token": LOCK_TOKEN,
        "llm_payload": CompressionFinalizeLlmPayload(
            compressed_context="new ctx",
            new_compressed_context_tokens=80,
        ),
    }
    data.update(overrides)
    return CompressionFinalizeInput.model_validate(data)


@pytest.mark.asyncio
async def test_archived_mismatch_raises_before_redis() -> None:
    with pytest.raises((CompressionFinalizeValidationError, ValidationError)):
        await finalize_compression(
            redis=MagicMock(),
            input=_input(archived_message_tokens=99),
        )


@pytest.mark.asyncio
async def test_empty_lock_token_raises() -> None:
    with pytest.raises((CompressionFinalizeValidationError, ValidationError)):
        await finalize_compression(
            redis=MagicMock(),
            input=_input(lock_owner_token=""),
        )


@pytest.mark.asyncio
async def test_service_success_path() -> None:
    mock_redis = MagicMock()
    with patch(
        "memory_system.domain.services.compression_finalize_service.finalize_compression_in_redis",
        new_callable=AsyncMock,
        return_value=CompressionFinalizeLuaOutcome(
            status=CompressionFinalizeStatus.SUCCESS,
            new_compression_version=1,
            new_estimated_tokens=500,
        ),
    ) as mock_lua:
        result = await finalize_compression(
            redis=mock_redis,
            input=_input(),
            clock=lambda: FIXED_NOW,
        )

    assert result.status == CompressionFinalizeStatus.SUCCESS
    assert result.new_compression_version == 1
    assert result.new_estimated_tokens == 500
    mock_lua.assert_awaited_once()
    assert mock_lua.await_args is not None
    call_kwargs = mock_lua.await_args.kwargs
    assert call_kwargs["updated_time"] == FIXED_NOW


@pytest.mark.asyncio
async def test_u1b_argv_mismatch_maps_pending_conflict() -> None:
    mock_redis = MagicMock()
    with patch(
        "memory_system.domain.services.compression_finalize_service.finalize_compression_in_redis",
        new_callable=AsyncMock,
        return_value=CompressionFinalizeLuaOutcome(
            status=CompressionFinalizeStatus.PENDING_CONFLICT,
        ),
    ):
        result = await finalize_compression(
            redis=mock_redis,
            input=_input(),
        )
    assert result.status == CompressionFinalizeStatus.PENDING_CONFLICT


@pytest.mark.asyncio
async def test_malformed_token_argv_maps_invalid_session_state() -> None:
    mock_redis = MagicMock()
    with patch(
        "memory_system.domain.services.compression_finalize_service.finalize_compression_in_redis",
        new_callable=AsyncMock,
        return_value=CompressionFinalizeLuaOutcome(
            status=CompressionFinalizeStatus.INVALID_SESSION_STATE,
        ),
    ):
        result = await finalize_compression(
            redis=mock_redis,
            input=_input(),
        )
    assert result.status == CompressionFinalizeStatus.INVALID_SESSION_STATE
