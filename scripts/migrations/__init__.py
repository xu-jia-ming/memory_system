"""Shared Migration Protocol and context for scripts/migrations/001–004.

Amendment 001 / SHOULD_FIX 5: all four migrations use the same ``upgrade(ctx)``
interface; ``ctx`` carries Settings plus shared client accessors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from elasticsearch import Elasticsearch
from neo4j import Driver
from pymongo import MongoClient

from memory_system.settings import Settings


@runtime_checkable
class MigrationContext(Protocol):
    """Minimal context passed to every migration ``upgrade(ctx)``."""

    @property
    def settings(self) -> Settings:
        """Application settings (connection strings and schema names)."""

    @property
    def mongo_client(self) -> MongoClient:  # type: ignore[type-arg]
        """Connected pymongo client."""

    @property
    def neo4j_driver(self) -> Driver:
        """Connected Neo4j driver."""

    @property
    def es_client(self) -> Elasticsearch:
        """Connected Elasticsearch (sync) client."""


@dataclass(frozen=True, slots=True)
class MigrationCtx:
    """Concrete MigrationContext used by the Runner."""

    settings: Settings
    mongo_client: MongoClient  # type: ignore[type-arg]
    neo4j_driver: Driver
    es_client: Elasticsearch


class MigrationModule(Protocol):
    """Every migration module must expose ``upgrade(ctx)``."""

    def upgrade(self, ctx: MigrationContext) -> None:
        """Apply this migration idempotently."""


__all__ = [
    "MigrationContext",
    "MigrationCtx",
    "MigrationModule",
]
