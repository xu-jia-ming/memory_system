"""Unit tests for entity alignment service (EXT-004)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from memory_system.domain.models.entity_alignment import (
    EntityAlignmentInput,
    EntityAlignmentOutcomeKind,
    EntityMatchKind,
    EntityNodeSnapshot,
)
from memory_system.domain.models.extraction_llm import (
    RESERVED_USER_ENTITY_ID,
    ExtractionEntityCandidate,
    ExtractionMemoryCandidate,
    ExtractionValidatedResult,
)
from memory_system.domain.services.entity_alignment_service import (
    EntityAlignmentService,
    build_alignment_input,
)
from memory_system.domain.services.entity_key import (
    compute_entity_key,
    normalize_entity_name,
    planned_user_entity_fields,
)
from memory_system.infrastructure.neo4j.entity_alignment_repository import (
    EntityGraphDataError,
    SecondaryMatchCandidate,
)


@dataclass
class FakeEntityAlignmentRepository:
    user_entity: EntityNodeSnapshot | None = None
    entity_key_hits: dict[str, EntityNodeSnapshot] = field(default_factory=dict)
    secondary_rows: dict[str, list[EntityNodeSnapshot]] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)
    fail_on: str | None = None

    async def find_user_entity(
        self, user_id: str, *, user_entity_id: str
    ) -> EntityNodeSnapshot | None:
        self.calls.append(f"find_user_entity:{user_id}:{user_entity_id}")
        if self.fail_on == "find_user_entity":
            raise RuntimeError("neo4j unavailable")
        return self.user_entity

    async def find_by_entity_keys(
        self, user_id: str, entity_keys: list[str]
    ) -> dict[str, EntityNodeSnapshot]:
        self.calls.append(f"find_by_entity_keys:{user_id}:{len(entity_keys)}")
        if self.fail_on == "find_by_entity_keys":
            raise RuntimeError("neo4j unavailable")
        return {
            key: self.entity_key_hits[key]
            for key in entity_keys
            if key in self.entity_key_hits
        }

    async def find_secondary_match_candidates(
        self, user_id: str, candidates: list[SecondaryMatchCandidate]
    ) -> dict[str, list[EntityNodeSnapshot]]:
        self.calls.append(f"find_secondary_match_candidates:{user_id}:{len(candidates)}")
        if self.fail_on == "find_secondary_match_candidates":
            raise RuntimeError("neo4j unavailable")
        return {
            candidate.local_entity_id: self.secondary_rows.get(candidate.local_entity_id, [])
            for candidate in candidates
        }


def _entity(
    local_entity_id: str,
    name: str,
    entity_type: str = "person",
    aliases: list[str] | None = None,
) -> ExtractionEntityCandidate:
    return ExtractionEntityCandidate(
        local_entity_id=local_entity_id,
        name=name,
        type=entity_type,  # type: ignore[arg-type]
        aliases=aliases or [],
    )


def _memory(
    subject: str = "user",
    object_entity_id: str | None = "entity_1",
) -> ExtractionMemoryCandidate:
    return ExtractionMemoryCandidate(
        memory_type="fact",
        content="synthetic content",
        subject_entity_id=subject,
        predicate="knows",
        object_entity_id=object_entity_id,
        object_value=None,
        event_status=None,
        start_time=None,
        end_time=None,
        original_time_text=None,
        confidence=0.9,
        source_message_ids=["msg_000001"],
        candidate_source_time=1,
        candidate_fingerprint="fp",
    )


def _snapshot(
    *,
    entity_id: str,
    user_id: str,
    entity_type: str,
    canonical_name: str,
    normalized_name: str | None = None,
    aliases: list[str] | None = None,
) -> EntityNodeSnapshot:
    normalized = normalized_name or normalize_entity_name(canonical_name)
    return EntityNodeSnapshot(
        entity_id=entity_id,
        user_id=user_id,
        entity_key=compute_entity_key(
            user_id=user_id,
            entity_type=entity_type,
            normalized_name=normalized,
        ),
        entity_type=entity_type,
        canonical_name=canonical_name,
        normalized_name=normalized,
        aliases=aliases or [],
    )


def _input(
    *,
    entities: list[ExtractionEntityCandidate],
    memories: list[ExtractionMemoryCandidate] | None = None,
    referenced: set[str] | None = None,
) -> EntityAlignmentInput:
    validated = ExtractionValidatedResult(entities=entities, memories=memories or [_memory()])
    return EntityAlignmentInput(
        task_id="task-1",
        archive_id="archive-1",
        user_id="user-1",
        entities=entities,
        referenced_local_entity_ids=referenced
        or build_alignment_input(
            task_id="task-1",
            archive_id="archive-1",
            user_id="user-1",
            validated=validated,
        ).referenced_local_entity_ids,
    )


@pytest.mark.asyncio
async def test_a1_happy_path_mixed_matches() -> None:
    repo = FakeEntityAlignmentRepository(
        user_entity=_snapshot(
            entity_id="user:user-1",
            user_id="user-1",
            entity_type="person",
            canonical_name="current_user",
            normalized_name="current_user",
        ),
        entity_key_hits={
            compute_entity_key(
                user_id="user-1",
                entity_type="project",
                normalized_name=normalize_entity_name("Memory System"),
            ): _snapshot(
                entity_id="entity-existing",
                user_id="user-1",
                entity_type="project",
                canonical_name="Memory System",
            )
        },
    )
    service = EntityAlignmentService(repo, entity_id_factory=lambda: "planned-id")
    outcome = await service.align(
        _input(
            entities=[
                _entity("entity_1", "Memory System", "project"),
                _entity("entity_2", "New Person", "person"),
            ]
        )
    )
    assert outcome.outcome == EntityAlignmentOutcomeKind.SUCCESS
    assert outcome.success is not None
    alignments = outcome.success.alignments
    assert alignments[0].local_entity_id == RESERVED_USER_ENTITY_ID
    assert alignments[1].match_kind == EntityMatchKind.ENTITY_KEY_EXACT
    assert alignments[2].match_kind == EntityMatchKind.PLANNED_CREATE
    assert outcome.success.local_entity_id_map()["entity_1"] == "entity-existing"


@pytest.mark.asyncio
async def test_a2_planned_create_path() -> None:
    repo = FakeEntityAlignmentRepository()
    service = EntityAlignmentService(repo, entity_id_factory=lambda: "new-entity-id")
    outcome = await service.align(
        _input(
            entities=[_entity("entity_1", "Brand New", "concept")],
            memories=[_memory(subject="entity_1", object_entity_id=None)],
            referenced={"entity_1"},
        )
    )
    alignment = outcome.success.alignments[0]  # type: ignore[union-attr]
    assert alignment.match_kind == EntityMatchKind.PLANNED_CREATE
    assert alignment.planned_create is True
    assert alignment.existing_entity is None


@pytest.mark.asyncio
async def test_a3_entity_key_exact_hit() -> None:
    snapshot = _snapshot(
        entity_id="entity-1",
        user_id="user-1",
        entity_type="person",
        canonical_name="Alice",
    )
    repo = FakeEntityAlignmentRepository(entity_key_hits={snapshot.entity_key: snapshot})
    service = EntityAlignmentService(repo)
    outcome = await service.align(
        _input(
            entities=[_entity("entity_1", "Alice", "person")],
            memories=[_memory(subject="entity_1", object_entity_id=None)],
            referenced={"entity_1"},
        )
    )
    alignment = outcome.success.alignments[0]  # type: ignore[union-attr]
    assert alignment.match_kind == EntityMatchKind.ENTITY_KEY_EXACT
    assert alignment.canonical_name == "Alice"


@pytest.mark.asyncio
async def test_a4_secondary_canonical_hit() -> None:
    snapshot = _snapshot(
        entity_id="entity-z",
        user_id="user-1",
        entity_type="person",
        canonical_name="Bob",
        normalized_name="bob",
    )
    repo = FakeEntityAlignmentRepository(
        secondary_rows={"entity_1": [snapshot]},
    )
    service = EntityAlignmentService(repo)
    outcome = await service.align(
        _input(
            entities=[_entity("entity_1", "Bob", "person")],
            memories=[_memory(subject="entity_1", object_entity_id=None)],
            referenced={"entity_1"},
        )
    )
    alignment = outcome.success.alignments[0]  # type: ignore[union-attr]
    assert alignment.match_kind == EntityMatchKind.CANONICAL_OR_ALIAS_EXACT


@pytest.mark.asyncio
async def test_a4b_secondary_alias_hit() -> None:
    snapshot = _snapshot(
        entity_id="entity-1",
        user_id="user-1",
        entity_type="organization",
        canonical_name="ACME",
        normalized_name="acme",
        aliases=["  alice  "],
    )
    repo = FakeEntityAlignmentRepository(secondary_rows={"entity_1": [snapshot]})
    service = EntityAlignmentService(repo)
    outcome = await service.align(
        _input(
            entities=[_entity("entity_1", "Alice", "organization")],
            memories=[_memory(subject="entity_1", object_entity_id=None)],
            referenced={"entity_1"},
        )
    )
    alignment = outcome.success.alignments[0]  # type: ignore[union-attr]
    assert alignment.match_kind == EntityMatchKind.CANONICAL_OR_ALIAS_EXACT


@pytest.mark.asyncio
async def test_a5_secondary_miss_planned_create() -> None:
    repo = FakeEntityAlignmentRepository(secondary_rows={"entity_1": []})
    service = EntityAlignmentService(repo, entity_id_factory=lambda: "planned")
    outcome = await service.align(
        _input(
            entities=[_entity("entity_1", "Nobody", "person")],
            memories=[_memory(subject="entity_1", object_entity_id=None)],
            referenced={"entity_1"},
        )
    )
    assert outcome.success.alignments[0].match_kind == EntityMatchKind.PLANNED_CREATE  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_a5b_secondary_multi_hit_entity_id_asc() -> None:
    low = _snapshot(
        entity_id="a-entity",
        user_id="user-1",
        entity_type="person",
        canonical_name="Sam",
    )
    high = _snapshot(
        entity_id="z-entity",
        user_id="user-1",
        entity_type="person",
        canonical_name="Sam",
    )
    repo = FakeEntityAlignmentRepository(secondary_rows={"entity_1": [high, low]})
    service = EntityAlignmentService(repo)
    outcome = await service.align(
        _input(
            entities=[_entity("entity_1", "Sam", "person")],
            memories=[_memory(subject="entity_1", object_entity_id=None)],
            referenced={"entity_1"},
        )
    )
    assert outcome.success.alignments[0].entity_id == "a-entity"  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_a5c_same_batch_entity_key_collision() -> None:
    factory_calls = 0

    def factory() -> str:
        nonlocal factory_calls
        factory_calls += 1
        return f"planned-{factory_calls}"

    repo = FakeEntityAlignmentRepository()
    service = EntityAlignmentService(repo, entity_id_factory=factory)
    outcome = await service.align(
        _input(
            entities=[
                _entity("entity_1", "Same Name", "person"),
                _entity("entity_2", "Same Name", "person"),
            ],
            memories=[
                _memory(subject="entity_1", object_entity_id="entity_2"),
            ],
            referenced={"entity_1", "entity_2"},
        )
    )
    assert factory_calls == 1
    mapping = outcome.success.local_entity_id_map()  # type: ignore[union-attr]
    assert mapping["entity_1"] == mapping["entity_2"]


@pytest.mark.asyncio
async def test_a6_reserved_user_existing() -> None:
    repo = FakeEntityAlignmentRepository(
        user_entity=_snapshot(
            entity_id="user:user-1",
            user_id="user-1",
            entity_type="person",
            canonical_name="current_user",
            normalized_name="current_user",
        )
    )
    service = EntityAlignmentService(repo)
    outcome = await service.align(_input(entities=[]))
    user_alignment = outcome.success.alignments[0]  # type: ignore[union-attr]
    assert user_alignment.match_kind == EntityMatchKind.RESERVED_USER_EXISTING
    assert "find_by_entity_keys" not in " ".join(repo.calls)


@pytest.mark.asyncio
async def test_a7_reserved_user_planned_create() -> None:
    repo = FakeEntityAlignmentRepository(user_entity=None)
    service = EntityAlignmentService(repo)
    outcome = await service.align(_input(entities=[]))
    user_alignment = outcome.success.alignments[0]  # type: ignore[union-attr]
    assert user_alignment.match_kind == EntityMatchKind.RESERVED_USER_PLANNED_CREATE
    assert user_alignment.planned_alias_merge.planned_aliases == []


@pytest.mark.asyncio
async def test_a7b_memory_references_user_without_entity_row() -> None:
    repo = FakeEntityAlignmentRepository()
    service = EntityAlignmentService(repo)
    outcome = await service.align(_input(entities=[]))
    assert outcome.success.alignments[0].local_entity_id == RESERVED_USER_ENTITY_ID  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_a7c_entities_user_row_uses_s1_only() -> None:
    repo = FakeEntityAlignmentRepository()
    service = EntityAlignmentService(repo)
    outcome = await service.align(
        _input(
            entities=[_entity(RESERVED_USER_ENTITY_ID, "ignored", "person")],
        )
    )
    user_alignment = outcome.success.alignments[0]  # type: ignore[union-attr]
    assert user_alignment.match_kind == EntityMatchKind.RESERVED_USER_PLANNED_CREATE
    assert len(outcome.success.alignments) == 1  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_a8_no_user_reference_no_user_alignment() -> None:
    repo = FakeEntityAlignmentRepository()
    service = EntityAlignmentService(repo, entity_id_factory=lambda: "planned")
    outcome = await service.align(
        _input(
            entities=[_entity("entity_1", "Solo", "person")],
            memories=[_memory(subject="entity_1", object_entity_id=None)],
            referenced={"entity_1"},
        )
    )
    alignments = outcome.success.alignments  # type: ignore[union-attr]
    assert all(item.local_entity_id != RESERVED_USER_ENTITY_ID for item in alignments)


@pytest.mark.asyncio
async def test_a10_graph_query_failure() -> None:
    repo = FakeEntityAlignmentRepository(fail_on="find_by_entity_keys")
    service = EntityAlignmentService(repo)
    outcome = await service.align(
        _input(
            entities=[_entity("entity_1", "Alice", "person")],
            memories=[_memory(subject="entity_1", object_entity_id=None)],
            referenced={"entity_1"},
        ),
        attempt_count=2,
    )
    assert outcome.outcome == EntityAlignmentOutcomeKind.FAILURE
    assert outcome.failure is not None
    assert outcome.failure.error_code == "entity_alignment_failed"
    assert outcome.failure.failed_stage == "entity_alignment"
    assert outcome.success is None


@pytest.mark.asyncio
async def test_a11_graph_data_anomaly_failure() -> None:
    user_fields = planned_user_entity_fields("user-1")
    repo = FakeEntityAlignmentRepository(
        entity_key_hits={
            user_fields["entity_key"]: _snapshot(
                entity_id="user:user-1",
                user_id="user-1",
                entity_type="person",
                canonical_name="current_user",
                normalized_name="current_user",
            )
        },
    )
    service = EntityAlignmentService(repo)
    outcome = await service.align(
        _input(
            entities=[_entity("entity_1", "current_user", "person")],
            memories=[_memory(subject="entity_1", object_entity_id=None)],
            referenced={"entity_1"},
        )
    )
    assert outcome.outcome == EntityAlignmentOutcomeKind.FAILURE


@pytest.mark.asyncio
async def test_a12_forbidden_error_codes_absent() -> None:
    repo = FakeEntityAlignmentRepository(fail_on="find_by_entity_keys")
    service = EntityAlignmentService(repo)
    outcome = await service.align(
        _input(
            entities=[_entity("entity_1", "Alice", "person")],
            memories=[_memory(subject="entity_1", object_entity_id=None)],
            referenced={"entity_1"},
        )
    )
    dumped = outcome.model_dump(mode="json")
    forbidden = (
        "graph_query_failed",
        "reconciliation_plan_conflict",
        "graph_write_failed",
        "memory_search_text_too_long",
        "retrieval_index_write_failed",
        "llm_timeout",
        "archive_read",
    )
    for token in forbidden:
        assert token not in str(dumped)


@pytest.mark.asyncio
async def test_a14_replay_idempotent() -> None:
    repo = FakeEntityAlignmentRepository()
    service = EntityAlignmentService(repo, entity_id_factory=lambda: "planned-1")
    alignment_input = _input(
        entities=[_entity("entity_1", "Replay", "concept")],
        memories=[_memory(subject="entity_1", object_entity_id=None)],
        referenced={"entity_1"},
    )
    first = await service.align(alignment_input)
    second = await service.align(alignment_input)
    assert first.model_dump() == second.model_dump()


@pytest.mark.asyncio
async def test_a15_replay_after_entity_exists() -> None:
    snapshot = _snapshot(
        entity_id="entity-existing",
        user_id="user-1",
        entity_type="concept",
        canonical_name="Replay",
    )
    repo = FakeEntityAlignmentRepository()
    service = EntityAlignmentService(repo, entity_id_factory=lambda: "planned-1")
    alignment_input = _input(
        entities=[_entity("entity_1", "Replay", "concept")],
        memories=[_memory(subject="entity_1", object_entity_id=None)],
        referenced={"entity_1"},
    )
    planned = await service.align(alignment_input)
    assert planned.success.alignments[0].match_kind == EntityMatchKind.PLANNED_CREATE  # type: ignore[union-attr]

    repo.entity_key_hits[snapshot.entity_key] = snapshot
    replay = await service.align(alignment_input)
    assert replay.success.alignments[0].match_kind == EntityMatchKind.ENTITY_KEY_EXACT  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_a16_no_llm_imports() -> None:
    import memory_system.domain.services.entity_alignment_service as module

    source = module.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        content = handle.read()
    assert "infrastructure.llm" not in content


@pytest.mark.asyncio
async def test_a18_alias_merge_append() -> None:
    snapshot = _snapshot(
        entity_id="entity-1",
        user_id="user-1",
        entity_type="person",
        canonical_name="Alice",
        aliases=["Beta"],
    )
    repo = FakeEntityAlignmentRepository(entity_key_hits={snapshot.entity_key: snapshot})
    service = EntityAlignmentService(repo)
    outcome = await service.align(
        _input(
            entities=[_entity("entity_1", "Alice", "person", aliases=["alpha", "Beta"])],
            memories=[_memory(subject="entity_1", object_entity_id=None)],
            referenced={"entity_1"},
        )
    )
    merge = outcome.success.alignments[0].planned_alias_merge  # type: ignore[union-attr]
    assert merge.planned_aliases == ["Beta", "alpha"]
    assert merge.canonical_name_replaced is False


@pytest.mark.asyncio
async def test_a19_alias_merge_cap() -> None:
    existing = [f"alias-{index}" for index in range(50)]
    snapshot = _snapshot(
        entity_id="entity-1",
        user_id="user-1",
        entity_type="person",
        canonical_name="Alice",
        aliases=existing,
    )
    repo = FakeEntityAlignmentRepository(entity_key_hits={snapshot.entity_key: snapshot})
    service = EntityAlignmentService(repo, max_stored_entity_alias_count=50)
    outcome = await service.align(
        _input(
            entities=[_entity("entity_1", "Alice", "person", aliases=["new-a", "new-b"])],
            memories=[_memory(subject="entity_1", object_entity_id=None)],
            referenced={"entity_1"},
        )
    )
    merge = outcome.success.alignments[0].planned_alias_merge  # type: ignore[union-attr]
    assert len(merge.planned_aliases) == 50
    assert merge.omitted_alias_count == 2


@pytest.mark.asyncio
async def test_a20_candidate_name_not_added_to_aliases() -> None:
    repo = FakeEntityAlignmentRepository()
    service = EntityAlignmentService(repo, entity_id_factory=lambda: "planned")
    outcome = await service.align(
        _input(
            entities=[_entity("entity_1", "Unique Name", "person")],
            memories=[_memory(subject="entity_1", object_entity_id=None)],
            referenced={"entity_1"},
        )
    )
    merge = outcome.success.alignments[0].planned_alias_merge  # type: ignore[union-attr]
    assert "Unique Name" not in merge.planned_aliases


@pytest.mark.asyncio
async def test_a22_user_entity_alias_merge_disabled() -> None:
    repo = FakeEntityAlignmentRepository(
        user_entity=_snapshot(
            entity_id="user:user-1",
            user_id="user-1",
            entity_type="person",
            canonical_name="current_user",
            normalized_name="current_user",
            aliases=["keep"],
        )
    )
    service = EntityAlignmentService(repo)
    outcome = await service.align(
        _input(
            entities=[_entity(RESERVED_USER_ENTITY_ID, "ignored", "person", aliases=["x"])],
        )
    )
    merge = outcome.success.alignments[0].planned_alias_merge  # type: ignore[union-attr]
    assert merge.planned_aliases == ["keep"]


@pytest.mark.asyncio
async def test_a23_user_isolation_query_params() -> None:
    repo = FakeEntityAlignmentRepository()
    service = EntityAlignmentService(repo, entity_id_factory=lambda: "planned")
    await service.align(
        _input(
            entities=[_entity("entity_1", "Alice", "person")],
            memories=[_memory(subject="entity_1", object_entity_id=None)],
            referenced={"entity_1"},
        )
    )
    assert all("user-1" in call for call in repo.calls)


@pytest.mark.asyncio
async def test_a24_privacy_failure_logs(capsys: pytest.CaptureFixture[str]) -> None:
    repo = FakeEntityAlignmentRepository(fail_on="find_by_entity_keys")
    service = EntityAlignmentService(repo)
    await service.align(
        _input(
            entities=[_entity("entity_1", "Secret Name", "person")],
            memories=[_memory(subject="entity_1", object_entity_id=None)],
            referenced={"entity_1"},
        ),
        attempt_count=3,
    )
    captured = capsys.readouterr().out
    assert "Secret Name" not in captured
    assert "task-1" in captured
    assert "archive-1" in captured
    assert "user-1" in captured
    assert "entity_alignment" in captured


@pytest.mark.asyncio
async def test_a25_batch_queries_not_per_candidate() -> None:
    repo = FakeEntityAlignmentRepository()
    service = EntityAlignmentService(repo, entity_id_factory=lambda: "planned")
    entities = [_entity(f"entity_{index}", f"Name {index}", "person") for index in range(100)]
    await service.align(
        _input(
            entities=entities,
            memories=[_memory(subject="entity_0", object_entity_id=None)],
            referenced={entity.local_entity_id for entity in entities},
        )
    )
    entity_key_calls = [call for call in repo.calls if call.startswith("find_by_entity_keys")]
    secondary_calls = [
        call for call in repo.calls if call.startswith("find_secondary_match_candidates")
    ]
    assert len(entity_key_calls) == 1
    assert len(secondary_calls) == 1


@pytest.mark.asyncio
async def test_a26_read_only_repository_calls() -> None:
    repo = FakeEntityAlignmentRepository()
    service = EntityAlignmentService(repo, entity_id_factory=lambda: "planned")
    await service.align(
        _input(
            entities=[_entity("entity_1", "Alice", "person")],
            memories=[_memory(subject="entity_1", object_entity_id=None)],
            referenced={"entity_1"},
        )
    )
    allowed = {
        "find_user_entity",
        "find_by_entity_keys",
        "find_secondary_match_candidates",
    }
    for call in repo.calls:
        assert call.split(":")[0] in allowed


def test_entity_graph_data_error_is_exception() -> None:
    assert issubclass(EntityGraphDataError, Exception)
