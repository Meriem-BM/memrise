from datetime import datetime
from typing import Protocol

from memrise.core.graph import (
    GraphEdge,
    GraphPath,
    GraphProjection,
    GraphProjectionResult,
    GraphSearchRequest,
)


class GraphRepository(Protocol):
    async def is_available(self) -> bool: ...

    async def project(self, projection: GraphProjection) -> GraphProjectionResult: ...

    async def search(self, request: GraphSearchRequest) -> list[GraphPath]: ...

    async def get_neighborhood(
        self, *, node_uid: str, namespace_id: str, depth: int
    ) -> list[GraphPath]: ...

    async def update_edge_usefulness(self, edge_uid: str, usefulness_score: float) -> str | None:
        """Update the edge and return the claim_id backing it, when present."""
        ...

    async def expire_due_edges(self, *, now: datetime) -> int: ...

    async def list_edges_for_memory_version(
        self, *, namespace_id: str, memory_version_id: str
    ) -> list[GraphEdge]: ...
