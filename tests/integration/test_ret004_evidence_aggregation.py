"""Integration tests for RET-004 evidence aggregation with Neo4j."""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import time
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from neo4j import AsyncDriver, AsyncGraphDatabase
from tests.support.ret004_neo4j_fixtures import (
    MEMORY_NO_EVIDENCE,
    MEMORY_WITH_EVIDENCE,
    USER_RET004_A,
    seed_ret004_evidence_graph,
)

from memory_system.domain.models.authoritative_recall import (
    AuthoritativeRecallSuccess,
    ValidatedRetrievalCandidate,
)
from memory_system.domain.models.retrieval_memory_snapshot import (
    RetrievalEntitySnapshot,
    RetrievalMemorySnapshot,
)
from memory_system.domain.models.retrieval_scoring import (
    ActRScoreComponents,
    RetrievalScoringQuery,
)
from memory_system.domain.services.act_r_scoring import (
    compute_act_r_components,
    compute_final_score,
)
from memory_system.domain.services.retrieval_scoring_service import (
    RetrievalScoringService,
    create_retrieval_scoring_service,
)
from memory_system.infrastructure.neo4j.retrieval_evidence_read_repository import (
    RetrievalEvidenceReadError,
    RetrievalEvidenceReadRepository,
)
from memory_system.settings import get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
TEST_PROJECT = "memory-system-test"
NEO4J_CONTAINER = "memory-system-neo4j-test"
FIXED_CURRENT_TIME = 1_700_000_200
# NC-3 recency=0.4: age_days = 30 * log2(1/0.4) ≈ 39.848 → reference_time=0, current_time below
NC3_CURRENT_TIME = int(86400 * 30 * math.log(2.5) / math.log(2))


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(["docker", "info"], capture_output=True, check=False)
    return result.returncode == 0


def _compose_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("EMBEDDING_EFFECTIVE_RUNTIME_MODE", "cpu")
    env.setdefault("EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET", "4096")
    env["PROXY__HTTP_URL"] = ""
    return env


def _compose(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = [str(COMPOSE_SH), "--stack=test", "--embedding=none", *args]
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=_compose_env(),
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"compose failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _ensure_dotenv() -> None:
    dotenv = REPO_ROOT / ".env"
    if not dotenv.exists():
        shutil.copy(ENV_EXAMPLE, dotenv)


def _assert_test_isolation() -> None:
    config_result = _compose("config", "--format", "json")
    config: dict[str, Any] = json.loads(config_result.stdout)
    assert config.get("name") == TEST_PROJECT


def _container_ip(container: str) -> str | None:
    result = subprocess.run(
        [
            "docker",
            "inspect",
            "-f",
            "{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
            container,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    ip = result.stdout.strip()
    return ip or None


@pytest.fixture(scope="module")
def neo4j_uri() -> Iterator[str]:
    if not _docker_available():
        pytest.skip("Docker not available; cannot run RET-004 integration")
    _ensure_dotenv()
    try:
        _assert_test_isolation()
    except AssertionError as exc:
        pytest.skip(f"Test stack isolation not confirmed: {exc}")

    _compose("down", "-v", check=False)
    up = _compose("up", "-d", "neo4j", check=False)
    if up.returncode != 0:
        pytest.skip(
            "Unable to start compose test stack "
            f"(exit {up.returncode}): {up.stderr[-800:] or up.stdout[-800:]}"
        )

    deadline = time.time() + 180
    while time.time() < deadline:
        if _container_ip(NEO4J_CONTAINER):
            break
        time.sleep(2)
    else:
        _compose("down", "-v", check=False)
        pytest.skip("Test Neo4j container did not become ready in time")

    migrate = _compose("run", "--rm", "init-infra", check=False)
    if migrate.returncode != 0:
        _compose("down", "-v", check=False)
        pytest.skip(
            "init-infra migration failed: "
            f"{migrate.stderr[-800:] or migrate.stdout[-800:]}"
        )

    neo4j_ip = _container_ip(NEO4J_CONTAINER)
    if not neo4j_ip:
        _compose("down", "-v", check=False)
        pytest.skip("Could not resolve test Neo4j container IP")

    yield f"bolt://{neo4j_ip}:7687"
    _compose("down", "-v", check=False)


@pytest.fixture
async def neo4j_driver(neo4j_uri: str) -> AsyncIterator[AsyncDriver]:
    driver = AsyncGraphDatabase.driver(neo4j_uri)
    try:
        await driver.verify_connectivity()
    except Exception as exc:
        await driver.close()
        pytest.skip(f"Neo4j connectivity failed: {exc}")
    yield driver
    await driver.close()


@pytest.fixture(autouse=True)
async def _clean_graph(neo4j_driver: AsyncDriver) -> AsyncIterator[None]:
    async with neo4j_driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
    yield
    async with neo4j_driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")


def make_memory_snapshot(
    *,
    memory_id: str,
    user_id: str,
    importance: float,
    latest_source_time: int | None,
) -> RetrievalMemorySnapshot:
    return RetrievalMemorySnapshot(
        memory_id=memory_id,
        user_id=user_id,
        memory_type="fact",
        status="active",
        content=f"content-{memory_id}",
        subject_entity_id="entity-subject-a",
        predicate="works_on",
        object_entity_id=None,
        object_value=None,
        event_status=None,
        start_time=None,
        end_time=None,
        original_time_text=None,
        importance=importance,
        confidence=0.9,
        retrieval_count=1,
        last_retrieved_time=None,
        latest_source_time=latest_source_time,
        updated_time=FIXED_CURRENT_TIME,
        subject_entity=RetrievalEntitySnapshot(
            entity_id="entity-subject-a",
            canonical_name="Subject",
            aliases=[],
            entity_type="concept",
            normalized_name="subject",
        ),
        object_entity=None,
    )


def make_validated(
    *,
    memory_id: str,
    user_id: str,
    normalized_retrieval_score: float,
    importance: float,
    latest_source_time: int | None,
    candidate_origin: str = "direct",
    graph_retrieval_score: float | None = None,
) -> ValidatedRetrievalCandidate:
    return ValidatedRetrievalCandidate(
        memory_id=memory_id,
        bm25_rank=1,
        vector_rank=None,
        bm25_score=1.5,
        vector_score=None,
        retrieval_source=["bm25"],
        rrf_score=0.5,
        min_available_rank=1,
        normalized_retrieval_score=normalized_retrieval_score,
        graph_retrieval_score=graph_retrieval_score,
        candidate_origin=candidate_origin,  # type: ignore[arg-type]
        memory=make_memory_snapshot(
            memory_id=memory_id,
            user_id=user_id,
            importance=importance,
            latest_source_time=latest_source_time,
        ),
    )


@pytest.mark.asyncio
async def test_i1_evidence_count_and_source_message_ids(neo4j_driver: AsyncDriver) -> None:
    await seed_ret004_evidence_graph(neo4j_driver)
    settings = get_settings()
    service = create_retrieval_scoring_service(neo4j_driver=neo4j_driver, settings=settings)
    authoritative = AuthoritativeRecallSuccess(
        user_id=USER_RET004_A,
        retrieval_mode="hybrid",
        effective_channel_count=2,
        direct_candidates=[
            make_validated(
                memory_id=MEMORY_WITH_EVIDENCE,
                user_id=USER_RET004_A,
                normalized_retrieval_score=0.95,
                importance=0.95,
                latest_source_time=300,
            ),
        ],
        expanded_candidates=[],
        warnings=[],
    )
    outcome = await service.score(
        RetrievalScoringQuery(
            authoritative_success=authoritative,
            top_k=5,
            current_time=FIXED_CURRENT_TIME,
        )
    )
    assert outcome.outcome == "success"
    assert outcome.success is not None
    scored = outcome.success.scored_memories[0]
    assert scored.evidence_count == 3
    assert scored.source_message_ids == ["m3", "m2", "m1", "m4"]


@pytest.mark.asyncio
async def test_i2_user_isolation(neo4j_driver: AsyncDriver) -> None:
    await seed_ret004_evidence_graph(neo4j_driver)
    settings = get_settings()
    service = create_retrieval_scoring_service(neo4j_driver=neo4j_driver, settings=settings)
    authoritative = AuthoritativeRecallSuccess(
        user_id=USER_RET004_A,
        retrieval_mode="hybrid",
        effective_channel_count=2,
        direct_candidates=[
            make_validated(
                memory_id=MEMORY_WITH_EVIDENCE,
                user_id=USER_RET004_A,
                normalized_retrieval_score=0.95,
                importance=0.95,
                latest_source_time=300,
            ),
        ],
        expanded_candidates=[],
        warnings=[],
    )
    outcome = await service.score(
        RetrievalScoringQuery(
            authoritative_success=authoritative,
            top_k=5,
            current_time=FIXED_CURRENT_TIME,
        )
    )
    assert outcome.outcome == "success"
    assert outcome.success is not None
    message_ids = outcome.success.scored_memories[0].source_message_ids
    assert "user-b-msg" not in message_ids


@pytest.mark.asyncio
async def test_i3_single_batch_evidence_query(neo4j_driver: AsyncDriver) -> None:
    await seed_ret004_evidence_graph(neo4j_driver)
    settings = get_settings()
    retrieval_settings = settings.memory_retrieval
    repo = RetrievalEvidenceReadRepository(
        neo4j_driver,
        neo4j_timeout_seconds=float(retrieval_settings.neo4j_timeout_seconds),
    )
    service = RetrievalScoringService(evidence_repo=repo, settings=settings)

    with patch.object(
        repo,
        "load_evidence_for_memories",
        wraps=repo.load_evidence_for_memories,
    ) as spy:
        authoritative = AuthoritativeRecallSuccess(
            user_id=USER_RET004_A,
            retrieval_mode="hybrid",
            effective_channel_count=2,
            direct_candidates=[
                make_validated(
                    memory_id=MEMORY_WITH_EVIDENCE,
                    user_id=USER_RET004_A,
                    normalized_retrieval_score=0.95,
                    importance=0.95,
                    latest_source_time=300,
                ),
                make_validated(
                    memory_id=MEMORY_NO_EVIDENCE,
                    user_id=USER_RET004_A,
                    normalized_retrieval_score=0.5,
                    importance=0.5,
                    latest_source_time=50,
                ),
            ],
            expanded_candidates=[],
            warnings=[],
        )
        outcome = await service.score(
            RetrievalScoringQuery(
                authoritative_success=authoritative,
                top_k=2,
                current_time=FIXED_CURRENT_TIME,
            )
        )
        assert outcome.outcome == "success"
        assert spy.call_count == 1


@pytest.mark.asyncio
async def test_i4_memory_without_evidence(neo4j_driver: AsyncDriver) -> None:
    await seed_ret004_evidence_graph(neo4j_driver)
    settings = get_settings()
    service = create_retrieval_scoring_service(neo4j_driver=neo4j_driver, settings=settings)
    authoritative = AuthoritativeRecallSuccess(
        user_id=USER_RET004_A,
        retrieval_mode="hybrid",
        effective_channel_count=2,
        direct_candidates=[
            make_validated(
                memory_id=MEMORY_NO_EVIDENCE,
                user_id=USER_RET004_A,
                normalized_retrieval_score=0.5,
                importance=0.5,
                latest_source_time=50,
            ),
        ],
        expanded_candidates=[],
        warnings=[],
    )
    outcome = await service.score(
        RetrievalScoringQuery(
            authoritative_success=authoritative,
            top_k=5,
            current_time=FIXED_CURRENT_TIME,
        )
    )
    assert outcome.outcome == "success"
    assert outcome.success is not None
    scored = outcome.success.scored_memories[0]
    assert scored.evidence_count == 0
    assert scored.source_message_ids == []


@pytest.mark.asyncio
async def test_i5_act_r_score_matches_unit_case(neo4j_driver: AsyncDriver) -> None:
    await seed_ret004_evidence_graph(neo4j_driver)
    settings = get_settings()
    retrieval_settings = settings.memory_retrieval
    service = create_retrieval_scoring_service(neo4j_driver=neo4j_driver, settings=settings)
    # NC-3 aligned inputs: retrieval=0.8, importance=0.6, confidence=0.9, recency=0.4;
    # retrieval_count=4 → frequency closest to 0.5 (ln(5)/ln(21) ≈ 0.536).
    candidate = ValidatedRetrievalCandidate(
        memory_id=MEMORY_WITH_EVIDENCE,
        bm25_rank=1,
        vector_rank=None,
        bm25_score=1.5,
        vector_score=None,
        retrieval_source=["bm25"],
        rrf_score=0.5,
        min_available_rank=1,
        normalized_retrieval_score=0.8,
        graph_retrieval_score=None,
        candidate_origin="direct",
        memory=RetrievalMemorySnapshot(
            memory_id=MEMORY_WITH_EVIDENCE,
            user_id=USER_RET004_A,
            memory_type="fact",
            status="active",
            content="nc3 memory",
            subject_entity_id="entity-subject-a",
            predicate="works_on",
            object_entity_id=None,
            object_value=None,
            event_status=None,
            start_time=None,
            end_time=None,
            original_time_text=None,
            importance=0.6,
            confidence=0.9,
            retrieval_count=4,
            last_retrieved_time=None,
            latest_source_time=0,
            updated_time=FIXED_CURRENT_TIME,
            subject_entity=None,
            object_entity=None,
        ),
    )
    components = compute_act_r_components(candidate, NC3_CURRENT_TIME, retrieval_settings)
    assert components is not None
    expected_final_score = compute_final_score(components, "active", retrieval_settings)
    assert components.recency_score == pytest.approx(0.4, abs=1e-6)
    assert compute_final_score(
        ActRScoreComponents(
            retrieval_score=0.8,
            importance_score=0.6,
            confidence_score=0.9,
            frequency_score=0.5,
            recency_score=0.4,
        ),
        "active",
        retrieval_settings,
    ) == pytest.approx(0.71, abs=1e-6)
    authoritative = AuthoritativeRecallSuccess(
        user_id=USER_RET004_A,
        retrieval_mode="hybrid",
        effective_channel_count=2,
        direct_candidates=[candidate],
        expanded_candidates=[],
        warnings=[],
    )
    outcome = await service.score(
        RetrievalScoringQuery(
            authoritative_success=authoritative,
            top_k=1,
            current_time=NC3_CURRENT_TIME,
        )
    )
    assert outcome.outcome == "success"
    assert outcome.success is not None
    scored = outcome.success.scored_memories[0]
    assert scored.final_score == pytest.approx(expected_final_score, abs=1e-6)
    assert scored.act_r_components.recency_score == pytest.approx(0.4, abs=1e-6)
    assert scored.act_r_components.retrieval_score == pytest.approx(0.8, abs=1e-6)
    assert scored.act_r_components.importance_score == pytest.approx(0.6, abs=1e-6)
    assert scored.act_r_components.confidence_score == pytest.approx(0.9, abs=1e-6)


@pytest.mark.asyncio
async def test_f1_evidence_timeout_maps_to_graph_load_failed(
    neo4j_driver: AsyncDriver,
) -> None:
    settings = get_settings()
    failing_repo = AsyncMock()
    failing_repo.load_evidence_for_memories.side_effect = RetrievalEvidenceReadError(
        "neo4j evidence load timed out",
        retryable=True,
    )
    service = RetrievalScoringService(evidence_repo=failing_repo, settings=settings)
    authoritative = AuthoritativeRecallSuccess(
        user_id=USER_RET004_A,
        retrieval_mode="hybrid",
        effective_channel_count=2,
        direct_candidates=[
            make_validated(
                memory_id="mem-timeout",
                user_id=USER_RET004_A,
                normalized_retrieval_score=0.9,
                importance=0.8,
                latest_source_time=100,
            ),
        ],
        expanded_candidates=[],
        warnings=[],
    )
    outcome = await service.score(
        RetrievalScoringQuery(
            authoritative_success=authoritative,
            top_k=5,
            current_time=0,
        )
    )
    assert outcome.outcome == "failure"
    assert outcome.failure is not None
    assert outcome.failure.kind == "graph_load_failed"
