"""002 — Neo4j constraints and indexes (§2.1.9 exact names)."""

from __future__ import annotations

import logging

from scripts.migrations import MigrationContext

logger = logging.getLogger(__name__)

# Spec §2.1.9 — locked names; do not invent alternatives (Amendment 001 / SHOULD_FIX 1).
NEO4J_SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
FOR (e:Entity)
REQUIRE e.entity_id IS UNIQUE
""".strip(),
    """
CREATE CONSTRAINT entity_key_unique IF NOT EXISTS
FOR (e:Entity)
REQUIRE e.entity_key IS UNIQUE
""".strip(),
    """
CREATE CONSTRAINT memory_id_unique IF NOT EXISTS
FOR (m:Memory)
REQUIRE m.memory_id IS UNIQUE
""".strip(),
    """
CREATE CONSTRAINT evidence_id_unique IF NOT EXISTS
FOR (e:Evidence)
REQUIRE e.evidence_id IS UNIQUE
""".strip(),
    """
CREATE INDEX memory_user_type_status IF NOT EXISTS
FOR (m:Memory)
ON (m.user_id, m.memory_type, m.status)
""".strip(),
    """
CREATE INDEX memory_subject_predicate IF NOT EXISTS
FOR (m:Memory)
ON (m.user_id, m.subject_entity_id, m.predicate, m.status)
""".strip(),
)

EXPECTED_CONSTRAINT_NAMES: frozenset[str] = frozenset(
    {
        "entity_id_unique",
        "entity_key_unique",
        "memory_id_unique",
        "evidence_id_unique",
    }
)

EXPECTED_INDEX_NAMES: frozenset[str] = frozenset(
    {
        "memory_user_type_status",
        "memory_subject_predicate",
    }
)

NEO4J_SCHEMA_NAMES: tuple[str, ...] = (
    "entity_id_unique",
    "entity_key_unique",
    "memory_id_unique",
    "evidence_id_unique",
    "memory_user_type_status",
    "memory_subject_predicate",
)


def upgrade(ctx: MigrationContext) -> None:
    """Create §2.1.9 constraints/indexes with IF NOT EXISTS (idempotent)."""
    with ctx.neo4j_driver.session() as session:
        for statement in NEO4J_SCHEMA_STATEMENTS:
            session.run(statement)
    logger.info(
        "neo4j schema ensured: constraints=%s indexes=%s",
        sorted(EXPECTED_CONSTRAINT_NAMES),
        sorted(EXPECTED_INDEX_NAMES),
    )
