"""Compression LLM domain service (STM-007)."""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Literal

from pydantic import ValidationError

from memory_system.domain.models.compression_llm import (
    CompressionLlmFailure,
    CompressionLlmInput,
    CompressionLlmOutcome,
    CompressionLlmOutput,
    CompressionLlmResult,
    CompressionLlmSuccess,
)
from memory_system.domain.services.token_estimator import estimate_tokens
from memory_system.infrastructure.llm.compression_prompts import (
    COMPRESSION_PROMPT_VERSION,
    render_compression_prompts,
)
from memory_system.infrastructure.llm.errors import LlmServiceError
from memory_system.settings.models import Settings

if TYPE_CHECKING:
    from memory_system.infrastructure.llm.protocol import LLMClient

MAX_SCHEMA_ATTEMPTS = 2
_logger = logging.getLogger(__name__)


def _validate_input(input: CompressionLlmInput) -> str | None:
    if not input.archived_messages:
        return "archived_messages must not be empty"
    if input.max_compressed_context_estimated_tokens <= 0:
        return "max_compressed_context_estimated_tokens must be > 0"
    return None


def _is_blank_content(content: str) -> bool:
    return content.strip() == ""


FailureCode = Literal[
    "llm_empty_output",
    "llm_invalid_output",
    "compression_output_too_large",
    "llm_timeout",
    "llm_request_failed",
    "invalid_compression_input",
]


def _failure(
    *,
    error_code: FailureCode,
    model: str,
    attempt_count: int,
) -> CompressionLlmResult:
    return CompressionLlmResult(
        outcome=CompressionLlmOutcome.FAILURE,
        failure=CompressionLlmFailure(
            error_code=error_code,
            prompt_version=COMPRESSION_PROMPT_VERSION,
            model=model,
            attempt_count=attempt_count,
        ),
    )


async def run_compression_llm(
    input: CompressionLlmInput,
    llm_client: LLMClient,
    settings: Settings,
    *,
    request_id: str | None = None,
) -> CompressionLlmResult:
    """Run compression LLM with schema retry and token boundary checks."""
    compression_settings = settings.llm.compression
    model = compression_settings.model
    timeout_seconds = float(settings.context.compression_llm_timeout_seconds)
    max_output_tokens = compression_settings.max_output_tokens

    validation_error = _validate_input(input)
    if validation_error is not None:
        _log_outcome(
            request_id=request_id or input.request_id,
            model=model,
            outcome=CompressionLlmOutcome.FAILURE,
            error_code="invalid_compression_input",
            attempt_count=1,
            duration_ms=0,
        )
        return _failure(
            error_code="invalid_compression_input",
            model=model,
            attempt_count=1,
        )

    system_prompt, user_prompt = render_compression_prompts(
        existing_compressed_context=input.existing_compressed_context,
        archived_messages=input.archived_messages,
        max_compressed_context_estimated_tokens=input.max_compressed_context_estimated_tokens,
    )

    start = time.perf_counter()

    for attempt in range(MAX_SCHEMA_ATTEMPTS):
        attempt_number = attempt + 1
        try:
            raw_content = await llm_client.generate_structured(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout_seconds=timeout_seconds,
                max_output_tokens=max_output_tokens,
            )
        except LlmServiceError as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            mapped: FailureCode
            if exc.code == "llm_timeout":
                mapped = "llm_timeout"
            else:
                mapped = "llm_request_failed"
            _log_outcome(
                request_id=request_id or input.request_id,
                model=model,
                outcome=CompressionLlmOutcome.FAILURE,
                error_code=mapped,
                attempt_count=attempt_number,
                duration_ms=duration_ms,
            )
            return _failure(
                error_code=mapped,
                model=model,
                attempt_count=attempt_number,
            )

        if _is_blank_content(raw_content):
            duration_ms = int((time.perf_counter() - start) * 1000)
            _log_outcome(
                request_id=request_id or input.request_id,
                model=model,
                outcome=CompressionLlmOutcome.FAILURE,
                error_code="llm_empty_output",
                attempt_count=attempt_number,
                duration_ms=duration_ms,
            )
            return _failure(
                error_code="llm_empty_output",
                model=model,
                attempt_count=attempt_number,
            )

        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError:
            if attempt < MAX_SCHEMA_ATTEMPTS - 1:
                continue
            duration_ms = int((time.perf_counter() - start) * 1000)
            _log_outcome(
                request_id=request_id or input.request_id,
                model=model,
                outcome=CompressionLlmOutcome.FAILURE,
                error_code="llm_invalid_output",
                attempt_count=MAX_SCHEMA_ATTEMPTS,
                duration_ms=duration_ms,
            )
            return _failure(
                error_code="llm_invalid_output",
                model=model,
                attempt_count=MAX_SCHEMA_ATTEMPTS,
            )

        try:
            output = CompressionLlmOutput.model_validate(parsed)
        except ValidationError:
            if attempt < MAX_SCHEMA_ATTEMPTS - 1:
                continue
            duration_ms = int((time.perf_counter() - start) * 1000)
            _log_outcome(
                request_id=request_id or input.request_id,
                model=model,
                outcome=CompressionLlmOutcome.FAILURE,
                error_code="llm_invalid_output",
                attempt_count=MAX_SCHEMA_ATTEMPTS,
                duration_ms=duration_ms,
            )
            return _failure(
                error_code="llm_invalid_output",
                model=model,
                attempt_count=MAX_SCHEMA_ATTEMPTS,
            )

        new_tokens = estimate_tokens(output.compressed_context)
        if (
            output.compressed_context
            and new_tokens > input.max_compressed_context_estimated_tokens
        ):
            duration_ms = int((time.perf_counter() - start) * 1000)
            _log_outcome(
                request_id=request_id or input.request_id,
                model=model,
                outcome=CompressionLlmOutcome.FAILURE,
                error_code="compression_output_too_large",
                attempt_count=attempt_number,
                duration_ms=duration_ms,
            )
            return _failure(
                error_code="compression_output_too_large",
                model=model,
                attempt_count=attempt_number,
            )

        duration_ms = int((time.perf_counter() - start) * 1000)
        _log_outcome(
            request_id=request_id or input.request_id,
            model=model,
            outcome=CompressionLlmOutcome.SUCCESS,
            error_code=None,
            attempt_count=attempt_number,
            duration_ms=duration_ms,
        )
        return CompressionLlmResult(
            outcome=CompressionLlmOutcome.SUCCESS,
            success=CompressionLlmSuccess(
                compressed_context=output.compressed_context,
                new_compressed_context_tokens=new_tokens,
                prompt_version=COMPRESSION_PROMPT_VERSION,
                model=model,
            ),
        )

    raise RuntimeError("compression LLM attempt loop exhausted without result")


def _log_outcome(
    *,
    request_id: str | None,
    model: str,
    outcome: CompressionLlmOutcome,
    error_code: str | None,
    attempt_count: int,
    duration_ms: int,
) -> None:
    _logger.info(
        "compression_llm outcome=%s model=%s prompt_version=%s "
        "request_id=%s error_code=%s attempt_count=%s duration_ms=%s",
        outcome.value,
        model,
        COMPRESSION_PROMPT_VERSION,
        request_id,
        error_code,
        attempt_count,
        duration_ms,
    )
