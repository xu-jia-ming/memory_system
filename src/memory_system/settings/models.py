"""Pydantic Settings models for the Memory System MVP."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from memory_system.settings.sources import YamlSettingsSource
from memory_system.settings.validators import (
    validate_context,
    validate_memory_consolidation,
    validate_memory_retrieval,
    validate_shutdown,
)

_REQUIRED_ENV_KEYS: tuple[str, ...] = (
    "APP_ENV",
    "REDIS__URI",
    "MONGODB__URI",
    "KAFKA__BOOTSTRAP_SERVERS",
    "NEO4J__URI",
    "ELASTICSEARCH__URL",
    "LLM__BASE_URL",
    "LLM__API_KEY",
    "LLM__COMPRESSION__MODEL",
    "LLM__EXTRACTION__MODEL",
    "EMBEDDING__MODEL_ID",
    "EMBEDDING__BASE_URL",
    "MEMORY_API_KEY",
    "MEMORY_ADMIN_API_KEY",
    "PROXY__HTTP_URL",
    "EMBEDDING_EFFECTIVE_RUNTIME_MODE",
    "EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET",
)


class ContextSettings(BaseModel):
    compression_trigger_tokens: int = 5000
    compression_target_tokens: int = 3000
    preferred_recent_messages: int = 10
    absolute_min_recent_messages: int = 2
    max_compressed_context_estimated_tokens: int = 1000
    max_compression_rounds_per_request: int = 3
    max_message_estimated_tokens: int = 2000
    max_working_memory_estimated_tokens: int = 12000
    max_archive_estimated_tokens: int = 7000
    allowed_future_timestamp_skew_seconds: int = 300
    compression_llm_timeout_seconds: int = 120
    compression_lock_ttl_seconds: int = 420
    safety_margin_seconds: int = 30


class MemoryExtractionSettings(BaseModel):
    prompt_version: str = "memory_extraction_v1"
    llm_timeout_seconds: int = 120
    max_archive_estimated_tokens: int = 8000
    max_memory_candidates_per_archive: int = 50
    max_entity_candidates_per_archive: int = 100
    max_memory_content_characters: int = 512
    max_entity_name_characters: int = 128
    max_entity_alias_count_per_candidate: int = 32
    max_entity_alias_characters: int = 128
    max_predicate_characters: int = 64
    max_object_value_characters: int = 256
    max_original_time_text_characters: int = 128
    max_stored_entity_alias_count: int = 50
    max_search_text_tokens: int = 1024


class MemoryRetrievalSettings(BaseModel):
    elasticsearch_version: str = "9.4.4"
    physical_index_name: str = "memory_retrieval_v1"
    index_name: str = "memory_retrieval_current"
    embedding_provider: Literal["siliconflow", "local_tei"] = "siliconflow"
    siliconflow_base_url: str = "https://api.siliconflow.cn"
    embedding_model: str = "BAAI/bge-m3"
    embedding_model_revision: str = "57aacf8560157b7c1d4f771ce1a199877aeeec74"
    embedding_dimension: int = 1024
    embedding_max_input_tokens: int = 1024
    embedding_timeout_seconds: int = 10
    elasticsearch_timeout_seconds: int = 5
    neo4j_timeout_seconds: int = 5
    retrieval_total_timeout_seconds: int = 15
    bm25_top_n: int = 30
    vector_top_n: int = 30
    vector_num_candidates: int = 100
    fused_top_n: int = 30
    rrf_k: int = 60
    graph_expand_per_seed: int = 2
    max_graph_candidates: int = 20
    graph_decay: float = 0.60
    default_top_k: int = 10
    max_top_k: int = 20
    max_source_message_ids: int = 20
    recency_half_life_days: int = 30
    retrieval_score_weight: float = 0.55
    importance_weight: float = 0.15
    confidence_weight: float = 0.10
    frequency_weight: float = 0.10
    recency_weight: float = 0.10
    conflicted_penalty: float = 0.85
    superseded_penalty: float = 0.60


class MemoryConsolidationSettings(BaseModel):
    enabled: bool = True
    schedule_cron: str = "0 3 * * *"
    timezone: str = "UTC"
    scheduler_max_instances: int = 1
    scheduler_coalesce: bool = True
    scheduler_misfire_grace_time_seconds: int = 3600
    batch_size: int = 500
    evidence_saturation_count: int = 5
    profile_half_life_days: int = 365
    fact_half_life_days: int = 180
    preference_half_life_days: int = 120
    event_half_life_days: int = 60
    superseded_half_life_days: int = 30
    confidence_weight: float = 0.55
    evidence_weight: float = 0.45
    reinforcement_bonus_weight: float = 0.35
    min_importance: float = 0.05
    conflicted_min_importance: float = 0.30
    max_importance: float = 1.00


class LLMCompressionTaskSettings(BaseModel):
    model: str = "deepseek-v4-flash"
    thinking: str = "disabled"
    response_format: str = "json_object"
    temperature: int = 0
    max_output_tokens: int = 2048


class LLMExtractionTaskSettings(BaseModel):
    model: str = "deepseek-v4-flash"
    thinking: str = "disabled"
    response_format: str = "json_object"
    temperature: int = 0
    max_output_tokens: int = 8192


class LLMSettings(BaseModel):
    provider: str = "deepseek"
    base_url: str = "https://api.deepseek.com"
    api_mode: str = "openai_chat_completions"
    api_key: SecretStr
    compression: LLMCompressionTaskSettings = Field(default_factory=LLMCompressionTaskSettings)
    extraction: LLMExtractionTaskSettings = Field(default_factory=LLMExtractionTaskSettings)


class EmbeddingRuntimeBudgetSettings(BaseModel):
    client_total_token_budget: int
    tei_max_batch_tokens: int


class EmbeddingGpuSettings(EmbeddingRuntimeBudgetSettings):
    minimum_free_memory_mb: int = 8192


class EmbeddingConsistencySettings(BaseModel):
    minimum_cosine_similarity: float = 0.999


class EmbeddingSettings(BaseModel):
    model_id: str
    base_url: str
    max_client_batch_size: int = 64
    per_input_token_limit: int = 1024
    cpu: EmbeddingRuntimeBudgetSettings = Field(
        default_factory=lambda: EmbeddingRuntimeBudgetSettings(
            client_total_token_budget=4096,
            tei_max_batch_tokens=8192,
        )
    )
    gpu: EmbeddingGpuSettings = Field(
        default_factory=lambda: EmbeddingGpuSettings(
            client_total_token_budget=16384,
            tei_max_batch_tokens=16384,
            minimum_free_memory_mb=8192,
        )
    )
    consistency: EmbeddingConsistencySettings = Field(
        default_factory=EmbeddingConsistencySettings
    )


class KafkaSettings(BaseModel):
    bootstrap_servers: str
    topic: str = "context.archive.created"
    partitions: int = 3
    replication_factor: int = 1
    retention_ms: int = 604800000
    cleanup_policy: str = "delete"
    compression_type: str = "producer"
    max_message_bytes: int = 1048576


class KafkaProducerSettings(BaseModel):
    acks: str = "all"
    enable_idempotence: bool = True
    compression_type: str = "lz4"
    request_timeout_ms: int = 30000
    max_batch_size: int = 16384
    linger_ms: int = 10


class KafkaConsumerSettings(BaseModel):
    enable_auto_commit: bool = False
    auto_offset_reset: str = "earliest"
    session_timeout_ms: int = 30000
    heartbeat_interval_ms: int = 10000
    max_poll_interval_ms: int = 900000
    max_poll_records: int = 1


class HttpClientSettings(BaseModel):
    connect_timeout_seconds: int = 5
    read_timeout_seconds: int = 120
    write_timeout_seconds: int = 30
    pool_timeout_seconds: int = 5
    max_connections: int = 100
    max_keepalive_connections: int = 20


class EmbeddingHttpClientSettings(BaseModel):
    connect_timeout_seconds: int = 5
    read_timeout_seconds: int = 30


class RedisSettings(BaseModel):
    uri: SecretStr
    socket_connect_timeout_seconds: int = 3
    socket_timeout_seconds: int = 5
    max_connections: int = 50


class MongoDBSettings(BaseModel):
    uri: SecretStr
    server_selection_timeout_ms: int = 5000
    connect_timeout_ms: int = 5000
    max_pool_size: int = 50


class Neo4jSettings(BaseModel):
    uri: SecretStr
    connection_timeout_seconds: int = 5
    connection_acquisition_timeout_seconds: int = 10
    max_connection_pool_size: int = 50


class ElasticsearchSettings(BaseModel):
    url: str
    request_timeout_seconds: int = 10
    max_retries: int = 2
    retry_on_timeout: bool = True


class ProxySettings(BaseModel):
    http_url: str | None = None


class ShutdownSettings(BaseModel):
    memory_api_timeout_seconds: int = 450
    extraction_worker_timeout_seconds: int = 270
    consolidation_worker_timeout_seconds: int = 270


class Settings(BaseSettings):
    app_env: Literal["development", "test"] = "development"
    redis: RedisSettings
    mongodb: MongoDBSettings
    kafka: KafkaSettings
    neo4j: Neo4jSettings
    elasticsearch: ElasticsearchSettings
    llm: LLMSettings
    embedding: EmbeddingSettings
    memory_api_key: SecretStr
    memory_admin_api_key: SecretStr
    siliconflow_api_key: SecretStr | None = None
    proxy: ProxySettings = Field(default_factory=ProxySettings)
    embedding_effective_runtime_mode: Literal["cpu", "gpu"]
    embedding_client_total_token_budget: int = Field(gt=0)
    context: ContextSettings = Field(default_factory=ContextSettings)
    memory_extraction: MemoryExtractionSettings = Field(default_factory=MemoryExtractionSettings)
    memory_retrieval: MemoryRetrievalSettings = Field(default_factory=MemoryRetrievalSettings)
    memory_consolidation: MemoryConsolidationSettings = Field(
        default_factory=MemoryConsolidationSettings
    )
    kafka_producer: KafkaProducerSettings = Field(default_factory=KafkaProducerSettings)
    kafka_consumer: KafkaConsumerSettings = Field(default_factory=KafkaConsumerSettings)
    http_client: HttpClientSettings = Field(default_factory=HttpClientSettings)
    embedding_http_client: EmbeddingHttpClientSettings = Field(
        default_factory=EmbeddingHttpClientSettings
    )
    shutdown: ShutdownSettings = Field(default_factory=ShutdownSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        nested_model_default_partial_update=True,
        extra="ignore",
    )

    @field_validator("proxy", mode="before")
    @classmethod
    def _normalize_proxy(cls, value: object) -> object:
        if value is None or value == "":
            return {}
        return value

    @model_validator(mode="after")
    def _validate_cross_field_constraints(self) -> Settings:
        info = _SettingsValidationInfo(self)
        validate_context(self, info)  # type: ignore[arg-type]
        validate_memory_consolidation(self, info)  # type: ignore[arg-type]
        validate_memory_retrieval(self, info)  # type: ignore[arg-type]
        validate_shutdown(self, info)  # type: ignore[arg-type]
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        yaml_settings = YamlSettingsSource(settings_cls)
        # pydantic-settings 2.14 merges with deep_update(new_source, accumulated_state),
        # so earlier tuple entries win on conflicts. Order below yields:
        # env > dotenv > yaml_merged > init defaults.
        return (
            env_settings,
            dotenv_settings,
            yaml_settings,
            init_settings,
        )

    @classmethod
    def required_env_keys(cls) -> tuple[str, ...]:
        return _REQUIRED_ENV_KEYS


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


class _SettingsValidationInfo:
    def __init__(self, settings: Settings) -> None:
        self.data = {
            "context": settings.context,
            "memory_extraction": settings.memory_extraction,
            "memory_retrieval": settings.memory_retrieval,
            "memory_consolidation": settings.memory_consolidation,
            "shutdown": settings.shutdown,
            "siliconflow_api_key": settings.siliconflow_api_key,
        }
