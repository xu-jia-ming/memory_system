"""EXT-007 index_sync_memory_set expansion helpers (pure logic)."""

from __future__ import annotations

from memory_system.domain.models.entity_alignment import EntityAlignmentSuccess
from memory_system.domain.services.entity_key import build_user_entity_id


def extract_non_user_aligned_entity_ids(
    entity_alignment: EntityAlignmentSuccess,
    user_id: str,
) -> list[str]:
    """Return aligned entity_ids excluding the reserved user entity."""
    user_entity_id = build_user_entity_id(user_id)
    entity_ids: list[str] = []
    seen: set[str] = set()
    for alignment in entity_alignment.alignments:
        if alignment.entity_id == user_entity_id:
            continue
        if alignment.entity_id in seen:
            continue
        seen.add(alignment.entity_id)
        entity_ids.append(alignment.entity_id)
    return entity_ids


def expand_index_sync_memory_ids(
    *,
    seed_memory_ids: set[str],
    related_memory_ids: set[str],
    entity_linked_memory_ids: set[str],
) -> set[str]:
    """Merge seed, SUPERSEDES/CONFLICTS_WITH neighbors, and entity-linked memories."""
    return seed_memory_ids | related_memory_ids | entity_linked_memory_ids
