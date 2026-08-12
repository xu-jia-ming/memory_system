"""Unit tests for entity key normalization (EXT-004)."""

from __future__ import annotations

import hashlib

from memory_system.domain.services.entity_key import (
    build_user_entity_id,
    compute_entity_key,
    normalize_entity_alias,
    normalize_entity_name,
    planned_user_entity_fields,
)


def test_u1_entity_key_formula() -> None:
    user_id = "user-a"
    entity_type = "person"
    normalized_name = "alice"
    expected = hashlib.sha256(f"{user_id}:{entity_type}:{normalized_name}".encode()).hexdigest()
    assert compute_entity_key(
        user_id=user_id,
        entity_type=entity_type,
        normalized_name=normalized_name,
    ) == expected


def test_u2_nfkc_normalization() -> None:
    assert normalize_entity_name("Ａｌｉｃｅ") == "alice"


def test_u3_lower_not_casefold() -> None:
    assert normalize_entity_name("Straße") == "straße"
    assert normalize_entity_name("İstanbul") == "i̇stanbul"


def test_u4_whitespace_compression_and_strip() -> None:
    assert normalize_entity_name("  Alice \t\n Bob  ") == "alice bob"


def test_u5_normalization_order_fixed() -> None:
    assert normalize_entity_name("  ＡＢＣ\tＤＥＦ  ") == "abc def"


def test_u6_no_unauthorized_normalization() -> None:
    assert normalize_entity_name("ACME, Inc.") == "acme, inc."
    assert normalize_entity_name("Item #1") == "item #1"


def test_u7_user_entity_fixed_fields() -> None:
    user_id = "user-42"
    fields = planned_user_entity_fields(user_id)
    assert build_user_entity_id(user_id) == "user:user-42"
    assert fields["entity_id"] == "user:user-42"
    assert fields["entity_type"] == "person"
    assert fields["canonical_name"] == "current_user"
    assert fields["normalized_name"] == "current_user"
    assert fields["aliases"] == []
    assert fields["entity_key"] == compute_entity_key(
        user_id=user_id,
        entity_type="person",
        normalized_name="current_user",
    )
    assert "created_time" not in fields
    assert "updated_time" not in fields


def test_u8_different_user_ids_different_keys() -> None:
    key_a = compute_entity_key(user_id="user-a", entity_type="person", normalized_name="alice")
    key_b = compute_entity_key(user_id="user-b", entity_type="person", normalized_name="alice")
    assert key_a != key_b


def test_normalize_entity_alias_preserves_case() -> None:
    assert normalize_entity_alias("  Foo\tBar  ") == "Foo Bar"
    assert normalize_entity_alias("Ａｌｉｃｅ") == "Alice"
