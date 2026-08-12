"""Unit tests for index_sync_set_expander (EXT-007)."""

from __future__ import annotations

from memory_system.domain.models.entity_alignment import (
    AlignedEntity,
    EntityAlignmentSuccess,
    EntityMatchKind,
    PlannedEntityAliasMerge,
)
from memory_system.domain.services.entity_key import build_user_entity_id
from memory_system.domain.services.index_sync_set_expander import (
    expand_index_sync_memory_ids,
    extract_non_user_aligned_entity_ids,
)


def _aligned(entity_id: str, local_entity_id: str = "entity_1") -> AlignedEntity:
    return AlignedEntity(
        local_entity_id=local_entity_id,
        entity_id=entity_id,
        match_kind=EntityMatchKind.PLANNED_CREATE,
        entity_type="project",
        canonical_name="Project",
        normalized_name="project",
        entity_key="key-1",
        planned_alias_merge=PlannedEntityAliasMerge(
            normalized_candidate_aliases=[],
            existing_aliases=[],
            planned_aliases=[],
            omitted_alias_count=0,
        ),
        existing_entity=None,
        planned_create=True,
    )


def test_u5_expand_deduplicates_union() -> None:
    expanded = expand_index_sync_memory_ids(
        seed_memory_ids={"mem-a", "mem-b"},
        related_memory_ids={"mem-b", "mem-c"},
        entity_linked_memory_ids={"mem-c", "mem-d"},
    )
    assert expanded == {"mem-a", "mem-b", "mem-c", "mem-d"}


def test_extract_non_user_entity_ids_excludes_user_entity() -> None:
    user_id = "user-1"
    alignment = EntityAlignmentSuccess(
        user_id=user_id,
        alignments=[
            _aligned(build_user_entity_id(user_id), local_entity_id="user"),
            _aligned("entity-project", local_entity_id="entity_1"),
            _aligned("entity-project", local_entity_id="entity_1"),
        ],
    )
    assert extract_non_user_aligned_entity_ids(alignment, user_id) == ["entity-project"]
