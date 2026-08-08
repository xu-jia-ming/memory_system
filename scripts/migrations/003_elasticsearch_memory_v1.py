"""003 — Elasticsearch physical index mapping + alias (§2.2.4).

DEV-004 is the sole creator of memory_retrieval_v1 Mapping and Alias.
EXT-007 / RET-* must not create or modify Mapping.
"""

from __future__ import annotations

import logging
from typing import Any

from elasticsearch.exceptions import NotFoundError

from scripts.migrations import MigrationContext

logger = logging.getLogger(__name__)

# Spec §2.2.4 Mapping — exact structure; do not simplify.
MEMORY_RETRIEVAL_V1_MAPPINGS: dict[str, Any] = {
    "properties": {
        "memory_id": {"type": "keyword"},
        "user_id": {"type": "keyword"},
        "memory_type": {"type": "keyword"},
        "status": {"type": "keyword"},
        "content": {"type": "text", "analyzer": "cjk"},
        "search_text": {"type": "text", "analyzer": "cjk"},
        "predicate": {"type": "keyword"},
        "event_status": {"type": "keyword"},
        "latest_source_time": {"type": "long"},
        "updated_time": {"type": "long"},
        "embedding": {
            "type": "dense_vector",
            "dims": 1024,
            "element_type": "float",
            "index": True,
            "similarity": "cosine",
            "index_options": {
                "type": "int8_hnsw",
                "m": 16,
                "ef_construction": 128,
            },
        },
    }
}


def _field_mapping(properties: dict[str, Any], field: str) -> dict[str, Any]:
    value = properties.get(field)
    if not isinstance(value, dict):
        raise ValueError(f"mapping field {field!r} missing or not an object")
    return value


def assert_mapping_compatible(actual_mappings: dict[str, Any]) -> None:
    """Fail if existing mapping is incompatible with §2.2.4 (no silent overwrite)."""
    actual_props = actual_mappings.get("properties")
    if not isinstance(actual_props, dict):
        raise ValueError("existing index mapping missing properties")

    expected_props: dict[str, Any] = MEMORY_RETRIEVAL_V1_MAPPINGS["properties"]
    for field, expected in expected_props.items():
        actual = _field_mapping(actual_props, field)
        if actual.get("type") != expected.get("type"):
            raise ValueError(
                f"incompatible mapping for {field}: type "
                f"{actual.get('type')!r} != {expected.get('type')!r}"
            )
        if "analyzer" in expected and actual.get("analyzer") != expected["analyzer"]:
            raise ValueError(
                f"incompatible mapping for {field}: analyzer "
                f"{actual.get('analyzer')!r} != {expected['analyzer']!r}"
            )
        if expected.get("type") == "dense_vector":
            for key in ("dims", "element_type", "similarity"):
                if actual.get(key) != expected.get(key):
                    raise ValueError(
                        f"incompatible dense_vector.{key} for embedding: "
                        f"{actual.get(key)!r} != {expected.get(key)!r}"
                    )
            if actual.get("index") is not True:
                raise ValueError("incompatible dense_vector.index for embedding: expected true")
            actual_opts = actual.get("index_options")
            expected_opts = expected["index_options"]
            if not isinstance(actual_opts, dict):
                raise ValueError("embedding.index_options missing")
            for opt_key in ("type", "m", "ef_construction"):
                if actual_opts.get(opt_key) != expected_opts.get(opt_key):
                    raise ValueError(
                        f"incompatible embedding.index_options.{opt_key}: "
                        f"{actual_opts.get(opt_key)!r} != {expected_opts.get(opt_key)!r}"
                    )


def upgrade(ctx: MigrationContext) -> None:
    """Create physical index + alias; compatible re-run succeeds; incompatible fails."""
    physical = ctx.settings.memory_retrieval.physical_index_name
    alias = ctx.settings.memory_retrieval.index_name
    es = ctx.es_client

    if es.indices.exists(index=physical):
        mapping_resp = es.indices.get_mapping(index=physical)
        index_body = mapping_resp.get(physical) or next(iter(mapping_resp.values()))
        mappings = index_body.get("mappings") if isinstance(index_body, dict) else None
        if not isinstance(mappings, dict):
            raise ValueError(f"unable to read mappings for index {physical}")
        assert_mapping_compatible(mappings)
        logger.info("elasticsearch index %s exists and mapping is compatible", physical)
    else:
        es.indices.create(index=physical, mappings=MEMORY_RETRIEVAL_V1_MAPPINGS)
        logger.info("elasticsearch index %s created with §2.2.4 mapping", physical)

    try:
        alias_resp: dict[str, Any] = dict(es.indices.get_alias(name=alias))
    except NotFoundError:
        alias_resp = {}

    if alias_resp:
        bound_indices = set(alias_resp.keys())
        if bound_indices == {physical}:
            logger.info("elasticsearch alias %s already bound to %s", alias, physical)
            return
        raise RuntimeError(
            f"alias {alias!r} is bound to {sorted(bound_indices)!r}, "
            f"expected only {physical!r}; refusing silent remapping"
        )

    es.indices.update_aliases(actions=[{"add": {"index": physical, "alias": alias}}])
    logger.info("elasticsearch alias %s added -> %s", alias, physical)
