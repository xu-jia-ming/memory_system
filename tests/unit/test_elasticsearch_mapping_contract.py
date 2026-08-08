"""Unit contract: Elasticsearch §2.2.4 Mapping constant structure."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

_mod = importlib.import_module("scripts.migrations.003_elasticsearch_memory_v1")
MEMORY_RETRIEVAL_V1_MAPPINGS: dict[str, Any] = _mod.MEMORY_RETRIEVAL_V1_MAPPINGS
assert_mapping_compatible: Callable[[dict[str, Any]], None] = _mod.assert_mapping_compatible


def test_mapping_keyword_and_cjk_fields() -> None:
    props = MEMORY_RETRIEVAL_V1_MAPPINGS["properties"]
    for field in ("memory_id", "user_id", "memory_type", "status", "predicate", "event_status"):
        assert props[field]["type"] == "keyword"
    for field in ("content", "search_text"):
        assert props[field]["type"] == "text"
        assert props[field]["analyzer"] == "cjk"
    for field in ("latest_source_time", "updated_time"):
        assert props[field]["type"] == "long"


def test_mapping_dense_vector_int8_hnsw() -> None:
    emb = MEMORY_RETRIEVAL_V1_MAPPINGS["properties"]["embedding"]
    assert emb["type"] == "dense_vector"
    assert emb["dims"] == 1024
    assert emb["element_type"] == "float"
    assert emb["index"] is True
    assert emb["similarity"] == "cosine"
    opts = emb["index_options"]
    assert opts["type"] == "int8_hnsw"
    assert opts["m"] == 16
    assert opts["ef_construction"] == 128


def test_assert_mapping_compatible_rejects_wrong_dims() -> None:
    props: dict[str, Any] = {}
    for key, value in MEMORY_RETRIEVAL_V1_MAPPINGS["properties"].items():
        props[key] = dict(value) if isinstance(value, dict) else value
    emb = dict(props["embedding"])
    emb["dims"] = 768
    emb["index_options"] = dict(emb["index_options"])
    props["embedding"] = emb
    try:
        assert_mapping_compatible({"properties": props})
        raised = False
    except ValueError:
        raised = True
    assert raised
