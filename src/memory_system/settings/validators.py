"""Cross-field configuration validators aligned with the technical specification."""

from __future__ import annotations

from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]
from pydantic import ValidationInfo

MEMORY_API_COMPOSE_GRACE_SECONDS = 480
EXTRACTION_WORKER_COMPOSE_GRACE_SECONDS = 300
CONSOLIDATION_WORKER_COMPOSE_GRACE_SECONDS = 300

_WEIGHT_TOLERANCE = 1e-6


def validate_context(settings: object, info: ValidationInfo) -> None:
    context = info.data.get("context")
    memory_extraction = info.data.get("memory_extraction")
    if context is None or memory_extraction is None:
        return

    if not (0 < context.absolute_min_recent_messages <= context.preferred_recent_messages):
        raise ValueError(
            "context.absolute_min_recent_messages must be > 0 and "
            "<= context.preferred_recent_messages"
        )

    if not (
        context.max_message_estimated_tokens
        <= context.max_archive_estimated_tokens
        <= memory_extraction.max_archive_estimated_tokens
    ):
        raise ValueError(
            "context.max_message_estimated_tokens must be <= context.max_archive_estimated_tokens "
            "<= memory_extraction.max_archive_estimated_tokens"
        )

    if not (
        context.max_compressed_context_estimated_tokens < context.compression_trigger_tokens
    ):
        raise ValueError(
            "context.max_compressed_context_estimated_tokens must be < "
            "context.compression_trigger_tokens"
        )

    if not (
        context.compression_target_tokens
        < context.compression_trigger_tokens
        < context.max_working_memory_estimated_tokens
    ):
        raise ValueError(
            "context.compression_target_tokens must be < context.compression_trigger_tokens "
            "< context.max_working_memory_estimated_tokens"
        )

    if not (
        context.max_message_estimated_tokens < context.max_working_memory_estimated_tokens
    ):
        raise ValueError(
            "context.max_message_estimated_tokens must be < "
            "context.max_working_memory_estimated_tokens"
        )

    lock_minimum = (
        context.max_compression_rounds_per_request * context.compression_llm_timeout_seconds
        + context.safety_margin_seconds
    )
    if not (context.compression_lock_ttl_seconds > lock_minimum):
        raise ValueError(
            "context.compression_lock_ttl_seconds must be greater than "
            "max_compression_rounds_per_request * compression_llm_timeout_seconds + "
            "safety_margin_seconds"
        )


def validate_memory_consolidation(settings: object, info: ValidationInfo) -> None:
    consolidation = info.data.get("memory_consolidation")
    if consolidation is None:
        return

    if consolidation.batch_size <= 0:
        raise ValueError("memory_consolidation.batch_size must be a positive integer")
    if consolidation.evidence_saturation_count <= 0:
        raise ValueError(
            "memory_consolidation.evidence_saturation_count must be a positive integer"
        )
    if consolidation.scheduler_max_instances <= 0:
        raise ValueError(
            "memory_consolidation.scheduler_max_instances must be a positive integer"
        )

    half_lives = (
        consolidation.profile_half_life_days,
        consolidation.fact_half_life_days,
        consolidation.preference_half_life_days,
        consolidation.event_half_life_days,
        consolidation.superseded_half_life_days,
    )
    if any(value <= 0 for value in half_lives):
        raise ValueError("memory_consolidation half-life values must be greater than 0")

    weight_sum = consolidation.confidence_weight + consolidation.evidence_weight
    if abs(weight_sum - 1.0) > _WEIGHT_TOLERANCE:
        raise ValueError("memory_consolidation.confidence_weight + evidence_weight must equal 1.0")

    bounded_weights = (
        consolidation.confidence_weight,
        consolidation.evidence_weight,
        consolidation.reinforcement_bonus_weight,
        consolidation.min_importance,
        consolidation.conflicted_min_importance,
        consolidation.max_importance,
    )
    if any(value < 0.0 or value > 1.0 for value in bounded_weights):
        raise ValueError(
            "memory_consolidation weights and importance bounds must be within [0.0, 1.0]"
        )

    if not (
        consolidation.min_importance
        <= consolidation.conflicted_min_importance
        <= consolidation.max_importance
    ):
        raise ValueError(
            "memory_consolidation.min_importance must be <= conflicted_min_importance "
            "<= max_importance"
        )

    try:
        CronTrigger.from_crontab(
            consolidation.schedule_cron,
            timezone=consolidation.timezone,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "memory_consolidation.schedule_cron and timezone must be valid for CronTrigger"
        ) from exc

    if consolidation.scheduler_misfire_grace_time_seconds <= 0:
        raise ValueError(
            "memory_consolidation.scheduler_misfire_grace_time_seconds must be greater than 0"
        )
    if not isinstance(consolidation.scheduler_coalesce, bool):
        raise ValueError("memory_consolidation.scheduler_coalesce must be a boolean")


def validate_memory_retrieval(settings: object, info: ValidationInfo) -> None:
    retrieval = info.data.get("memory_retrieval")
    if retrieval is None:
        return

    positive_int_fields = (
        "bm25_top_n",
        "vector_top_n",
        "vector_num_candidates",
        "fused_top_n",
        "graph_expand_per_seed",
        "max_graph_candidates",
        "default_top_k",
        "max_top_k",
        "max_source_message_ids",
        "recency_half_life_days",
    )
    for field_name in positive_int_fields:
        if getattr(retrieval, field_name) <= 0:
            raise ValueError(f"memory_retrieval.{field_name} must be a positive integer")

    if retrieval.vector_num_candidates < retrieval.vector_top_n:
        raise ValueError(
            "memory_retrieval.vector_num_candidates must be >= memory_retrieval.vector_top_n"
        )
    if retrieval.fused_top_n < retrieval.max_top_k:
        raise ValueError("memory_retrieval.fused_top_n must be >= memory_retrieval.max_top_k")

    score_weights = (
        retrieval.retrieval_score_weight,
        retrieval.importance_weight,
        retrieval.confidence_weight,
        retrieval.frequency_weight,
        retrieval.recency_weight,
    )
    if abs(sum(score_weights) - 1.0) > _WEIGHT_TOLERANCE:
        raise ValueError("memory_retrieval scoring weights must sum to 1.0")

    for weight in score_weights:
        if weight < 0.0 or weight > 1.0:
            raise ValueError("memory_retrieval scoring weights must be within [0.0, 1.0]")

    penalty_fields = (
        retrieval.graph_decay,
        retrieval.conflicted_penalty,
        retrieval.superseded_penalty,
    )
    for field_name, value in zip(
        ("graph_decay", "conflicted_penalty", "superseded_penalty"),
        penalty_fields,
        strict=True,
    ):
        if value < 0.0 or value > 1.0:
            raise ValueError(f"memory_retrieval.{field_name} must be within [0.0, 1.0]")

    if retrieval.embedding_dimension != 1024:
        raise ValueError("memory_retrieval.embedding_dimension must equal 1024")

    timeout_fields = (
        retrieval.embedding_timeout_seconds,
        retrieval.elasticsearch_timeout_seconds,
        retrieval.neo4j_timeout_seconds,
        retrieval.retrieval_total_timeout_seconds,
    )
    if any(value <= 0 for value in timeout_fields):
        raise ValueError("memory_retrieval timeout values must be positive")

    stage_timeouts = (
        retrieval.embedding_timeout_seconds,
        retrieval.elasticsearch_timeout_seconds,
        retrieval.neo4j_timeout_seconds,
    )
    if any(value > retrieval.retrieval_total_timeout_seconds for value in stage_timeouts):
        raise ValueError(
            "memory_retrieval stage timeouts must be <= retrieval_total_timeout_seconds"
        )

    siliconflow_api_key = info.data.get("siliconflow_api_key")
    if retrieval.embedding_provider == "siliconflow":
        if siliconflow_api_key is None or not siliconflow_api_key.get_secret_value().strip():
            raise ValueError(
                "SILICONFLOW_API_KEY is required when memory_retrieval.embedding_provider "
                "is siliconflow"
            )


def validate_shutdown(settings: object, info: ValidationInfo) -> None:
    shutdown = info.data.get("shutdown")
    context = info.data.get("context")
    if shutdown is None or context is None:
        return

    if shutdown.memory_api_timeout_seconds >= MEMORY_API_COMPOSE_GRACE_SECONDS:
        raise ValueError(
            "shutdown.memory_api_timeout_seconds must be less than "
            f"{MEMORY_API_COMPOSE_GRACE_SECONDS}"
        )
    if shutdown.extraction_worker_timeout_seconds >= EXTRACTION_WORKER_COMPOSE_GRACE_SECONDS:
        raise ValueError(
            "shutdown.extraction_worker_timeout_seconds must be less than "
            f"{EXTRACTION_WORKER_COMPOSE_GRACE_SECONDS}"
        )
    if shutdown.consolidation_worker_timeout_seconds >= CONSOLIDATION_WORKER_COMPOSE_GRACE_SECONDS:
        raise ValueError(
            "shutdown.consolidation_worker_timeout_seconds must be less than "
            f"{CONSOLIDATION_WORKER_COMPOSE_GRACE_SECONDS}"
        )
    if shutdown.memory_api_timeout_seconds <= context.compression_lock_ttl_seconds:
        raise ValueError(
            "shutdown.memory_api_timeout_seconds must be greater than "
            "context.compression_lock_ttl_seconds"
        )
