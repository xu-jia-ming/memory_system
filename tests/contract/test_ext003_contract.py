"""Contract tests for EXT-003 extraction LLM."""

from __future__ import annotations

import inspect
from collections.abc import Iterator
from typing import get_type_hints

import pytest
from tests.contract.helpers.extraction_llm_fake import valid_extraction_payload

from memory_system.domain.models.extraction_llm import (
    AUTHORIZED_ENTITY_FIELDS,
    ExtractionEntityCandidate,
    ExtractionLlmFailure,
    ExtractionMemoryCandidate,
)
from memory_system.domain.models.extraction_preprocessing import (
    ExtractionArchiveMessage,
    ExtractionReadyArchive,
)
from memory_system.domain.services.extraction_fingerprint import canonical_fingerprint_bytes
from memory_system.domain.services.extraction_llm_service import (
    EXTRACTION_SYSTEM_PROMPT,
    SCHEMA_CORRECTION_INSTRUCTION,
    validate_extraction_payload,
)
from memory_system.infrastructure.llm import DeepSeekLlmClient, LLMClient
from memory_system.settings import get_settings

VALID_ENV: dict[str, str] = {
    "APP_ENV": "test",
    "REDIS__URI": "redis://redis:6379/0",
    "MONGODB__URI": "mongodb://mongodb:27017/memory_system",
    "KAFKA__BOOTSTRAP_SERVERS": "kafka:9092",
    "NEO4J__URI": "neo4j://neo4j:7687",
    "ELASTICSEARCH__URL": "http://elasticsearch:9200",
    "LLM__BASE_URL": "https://api.deepseek.com",
    "LLM__API_KEY": "sk-example-replace-me",
    "LLM__COMPRESSION__MODEL": "deepseek-v4-flash",
    "LLM__EXTRACTION__MODEL": "deepseek-v4-flash",
    "EMBEDDING__MODEL_ID": "BAAI/bge-m3",
    "EMBEDDING__BASE_URL": "http://embedding-service:80",
    "MEMORY_API_KEY": "dev-memory-api-key-change-me",
    "MEMORY_ADMIN_API_KEY": "dev-memory-admin-key-change-me",
    "EMBEDDING_EFFECTIVE_RUNTIME_MODE": "cpu",
    "EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET": "4096",
    "SILICONFLOW_API_KEY": "sk-example-replace-me",
}


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)


def test_c1_extraction_ready_archive_field_set() -> None:
    hints = get_type_hints(ExtractionReadyArchive)
    assert set(hints) == {"archive_id", "user_id", "session_id", "messages"}


def test_c2_unknown_fields_stripped_before_persistence(valid_env: None) -> None:
    settings = get_settings()
    archive = ExtractionReadyArchive(
        archive_id="archive-1",
        user_id="user-1",
        session_id="session-1",
        messages=[],
    )
    payload = valid_extraction_payload()
    payload["unknown_top"] = True
    payload["entities"][0]["unknown_entity"] = True
    payload["memories"][0]["unknown_memory"] = True
    validated = validate_extraction_payload(
        payload,
        archive=archive.model_copy(
            update={
                "messages": [
                    ExtractionArchiveMessage(
                        message_id="msg_000001",
                        role="user",
                        content="x",
                        timestamp=1,
                    )
                ]
            }
        ),
        limits=settings.memory_extraction,
    )
    durable = validated.to_durable_dict()
    assert "unknown_top" not in durable
    assert "unknown_entity" not in durable["entities"][0]
    assert "unknown_memory" not in durable["memories"][0]


def test_c3_entity_fields_match_contract() -> None:
    assert AUTHORIZED_ENTITY_FIELDS == {
        "local_entity_id",
        "name",
        "type",
        "aliases",
    }
    fields = set(ExtractionEntityCandidate.model_fields)
    assert fields == AUTHORIZED_ENTITY_FIELDS


def test_c4_memory_fields_match_contract() -> None:
    llm_fields = {
        "memory_type",
        "content",
        "subject_entity_id",
        "predicate",
        "object_entity_id",
        "object_value",
        "event_status",
        "start_time",
        "end_time",
        "original_time_text",
        "confidence",
        "source_message_ids",
    }
    durable_fields = set(ExtractionMemoryCandidate.model_fields)
    assert llm_fields | {"candidate_source_time", "candidate_fingerprint"} == durable_fields


def test_c7_provider_settings_matrix(valid_env: None) -> None:
    settings = get_settings()
    assert settings.memory_extraction.prompt_version == "memory_extraction_v2"
    assert settings.memory_extraction.llm_timeout_seconds == 120
    assert settings.llm.extraction.model == "deepseek-v4-flash"
    assert settings.llm.extraction.max_output_tokens == 8192
    assert settings.llm.extraction.temperature == 0
    assert settings.llm.extraction.thinking == "disabled"


def test_c8_error_code_whitelist() -> None:
    hints = get_type_hints(ExtractionLlmFailure)
    assert set(hints["error_code"].__args__) == {
        "llm_timeout",
        "llm_request_failed",
        "llm_invalid_output",
    }


def test_c9_fingerprint_field_order(valid_env: None) -> None:
    canonical = canonical_fingerprint_bytes(
        memory_type="fact",
        content="c",
        subject_entity_id="user",
        predicate="likes",
        object_entity_id=None,
        object_value="tea",
        event_status=None,
        start_time=None,
        end_time=None,
        original_time_text=None,
        source_message_ids=["msg_z", "msg_a"],
    ).decode("utf-8")
    expected_prefix = (
        '["fact","c","user","likes",null,"tea",null,null,null,null,["msg_a","msg_z"]]'
    )
    assert canonical.startswith(expected_prefix)


def test_c10_durable_result_schema(valid_env: None) -> None:
    settings = get_settings()
    archive = ExtractionReadyArchive(
        archive_id="archive-1",
        user_id="user-1",
        session_id="session-1",
        messages=[
            ExtractionArchiveMessage(
                message_id="msg_000001",
                role="user",
                content="x",
                timestamp=1,
            )
        ],
    )
    validated = validate_extraction_payload(
        valid_extraction_payload(),
        archive=archive,
        limits=settings.memory_extraction,
    )
    durable = validated.to_durable_dict()
    assert set(durable) == {"entities", "memories"}
    assert "evidence_id" not in durable
    assert "entity_relations" not in durable


def test_c11_retry_contract_literals() -> None:
    assert "previous response was invalid" in SCHEMA_CORRECTION_INSTRUCTION.lower()
    assert EXTRACTION_SYSTEM_PROMPT.startswith("You are a long-term memory extraction engine.")
    for memory_type in ("fact", "preference", "event", "profile"):
        assert memory_type in EXTRACTION_SYSTEM_PROMPT
    assert "Classification order:" in EXTRACTION_SYSTEM_PROMPT


def test_llm_client_protocol_unchanged() -> None:
    signature = inspect.signature(LLMClient.generate_structured)
    assert list(signature.parameters) == [
        "self",
        "model",
        "system_prompt",
        "user_prompt",
        "timeout_seconds",
        "max_output_tokens",
    ]


def test_deepseek_supports_internal_extraction_profile(valid_env: None) -> None:
    signature = inspect.signature(DeepSeekLlmClient.generate_structured)
    assert "settings_profile" in signature.parameters
