"""Unit tests: Kafka LZ4 compression runtime (cramjam + aiokafka codec)."""

from __future__ import annotations

from collections.abc import Iterator

import cramjam  # type: ignore[import-untyped]
import pytest
from aiokafka import AIOKafkaProducer  # type: ignore[import-untyped]
from aiokafka.codec import has_lz4, lz4_decode, lz4_encode  # type: ignore[import-untyped]

from memory_system.settings import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_u1_cramjam_import_available() -> None:
    assert cramjam is not None
    version = getattr(cramjam, "__version__", None)
    assert version is not None
    assert tuple(int(part) for part in version.split(".")[:2]) >= (2, 8)


def test_u2_lz4_codec_round_trip_and_capability() -> None:
    assert has_lz4() is True
    payload = b"memory-system lz4 codec round-trip"
    compressed = lz4_encode(payload)
    assert compressed != payload
    assert lz4_decode(compressed) == payload


@pytest.mark.asyncio
async def test_u2_aiokafka_producer_lz4_initializes_without_runtime_error() -> None:
    producer = AIOKafkaProducer(
        bootstrap_servers="localhost:9092",
        compression_type="lz4",
    )
    assert producer._compression_type == "lz4"  # noqa: SLF001 — wire-level contract


def test_u3_authoritative_kafka_producer_compression_type_is_lz4(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KAFKA_PRODUCER__COMPRESSION_TYPE", raising=False)
    settings = get_settings()
    assert settings.kafka_producer.compression_type == "lz4"
