"""EXT-004 deterministic entity key and normalization helpers."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import TypedDict

_WHITESPACE = re.compile(r"\s+", re.UNICODE)


def normalize_entity_name(name: str) -> str:
    """§5.2 S2: NFKC → lower → whitespace compress → strip."""
    normalized = unicodedata.normalize("NFKC", name)
    normalized = normalized.lower()
    normalized = _WHITESPACE.sub(" ", normalized)
    return normalized.strip()


def normalize_entity_alias(alias: str) -> str:
    """§5.2.2 / §5.5: NFKC → whitespace compress → strip (no lower)."""
    normalized = unicodedata.normalize("NFKC", alias)
    normalized = _WHITESPACE.sub(" ", normalized)
    return normalized.strip()


def compute_entity_key(*, user_id: str, entity_type: str, normalized_name: str) -> str:
    """§5.2 entity_key = lowercase_hex(SHA256(utf8(user_id:entity_type:normalized_name)))."""
    payload = f"{user_id}:{entity_type}:{normalized_name}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_user_entity_id(user_id: str) -> str:
    """§2.1.10.1 reserved user entity_id."""
    return f"user:{user_id}"


class PlannedUserEntityFields(TypedDict):
    entity_id: str
    user_id: str
    entity_key: str
    entity_type: str
    canonical_name: str
    normalized_name: str
    aliases: list[str]


def planned_user_entity_fields(user_id: str) -> PlannedUserEntityFields:
    """§5.4 fixed fields for reserved user entity planned create (no server times)."""
    normalized_name = "current_user"
    entity_type = "person"
    return {
        "entity_id": build_user_entity_id(user_id),
        "user_id": user_id,
        "entity_key": compute_entity_key(
            user_id=user_id,
            entity_type=entity_type,
            normalized_name=normalized_name,
        ),
        "entity_type": entity_type,
        "canonical_name": "current_user",
        "normalized_name": normalized_name,
        "aliases": [],
    }
