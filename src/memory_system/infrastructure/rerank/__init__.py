"""Rerank client infrastructure."""

from memory_system.infrastructure.rerank.errors import RerankServiceError
from memory_system.infrastructure.rerank.factory import NoOpRerankClient, create_rerank_client
from memory_system.infrastructure.rerank.siliconflow_client import SiliconFlowRerankClient
from memory_system.infrastructure.rerank.types import (
    RerankClient,
    RerankResult,
    RerankScoredDocument,
)

__all__ = [
    "NoOpRerankClient",
    "RerankClient",
    "RerankResult",
    "RerankScoredDocument",
    "RerankServiceError",
    "SiliconFlowRerankClient",
    "create_rerank_client",
]
