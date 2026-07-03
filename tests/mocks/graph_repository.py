from dataclasses import dataclass, field
from datetime import datetime

from memrise.core.graph import (
    GraphEdge,
    GraphPath,
    GraphProjection,
    GraphProjectionResult,
    GraphSearchRequest,
)


@dataclass
class GraphRepositoryStub:
    available: bool = True
    paths: list[GraphPath] = field(default_factory=list)
    edges_by_version: dict[str, list[GraphEdge]] = field(default_factory=dict)
    neighborhood_paths: list[GraphPath] = field(default_factory=list)
    projected: list[GraphProjection] = field(default_factory=list)
    usefulness_updates: list[tuple[str, float]] = field(default_factory=list)
    claim_id_by_edge: dict[str, str] = field(default_factory=dict)
    expired_edge_count: int = 0

    async def is_available(self) -> bool:
        return self.available

    async def project(self, projection: GraphProjection) -> GraphProjectionResult:
        self.projected.append(projection)
        return GraphProjectionResult(
            memory_version_id=projection.memory_version_id,
            node_uids=tuple(node.temporary_id for node in projection.nodes),
            edge_uids=tuple(
                f"edge-{edge.source}-{edge.relation}-{edge.target}" for edge in projection.edges
            ),
            superseded_edge_count=0,
        )

    async def search(self, request: GraphSearchRequest) -> list[GraphPath]:
        del request
        return list(self.paths)

    async def get_neighborhood(
        self, *, node_uid: str, namespace_id: str, depth: int
    ) -> list[GraphPath]:
        del node_uid, namespace_id, depth
        return list(self.neighborhood_paths)

    async def update_edge_usefulness(self, edge_uid: str, usefulness_score: float) -> str | None:
        self.usefulness_updates.append((edge_uid, usefulness_score))
        return self.claim_id_by_edge.get(edge_uid)

    async def expire_due_edges(self, *, now: datetime) -> int:
        del now
        return self.expired_edge_count

    async def list_edges_for_memory_version(
        self, *, namespace_id: str, memory_version_id: str
    ) -> list[GraphEdge]:
        del namespace_id
        return list(self.edges_by_version.get(memory_version_id, []))


@dataclass
class ExplanationGraphRepository(GraphRepositoryStub):
    async def list_edges_for_memory_version(
        self, *, namespace_id: str, memory_version_id: str
    ) -> list[GraphEdge]:
        return await super().list_edges_for_memory_version(
            namespace_id=namespace_id,
            memory_version_id=memory_version_id,
        )
