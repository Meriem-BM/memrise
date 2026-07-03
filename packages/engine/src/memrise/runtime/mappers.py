from dataclasses import asdict

from memrise.core.graph import GraphPath
from memrise.core.models import BackgroundJob, CanonicalMemory, RetrievalItem
from memrise.ports.providers import TokenCounter
from memrise.ports.repositories import MemoryStore
from memrise.schemas.mappers import memory_to_summary
from memrise.schemas.responses import (
    GraphEdgeSummary,
    GraphNeighborhoodResponse,
    GraphNodeSummary,
    JobSummary,
    MemorySummary,
    RetrievalItemSummary,
    RetrievedMemory,
)


def to_job_summary(job: BackgroundJob) -> JobSummary:
    return JobSummary(
        id=job.id,
        type=job.type,
        status=job.status,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        run_at=job.run_at,
        locked_at=job.locked_at,
        locked_by=job.locked_by,
        last_error=job.last_error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def to_memory_summary(memory: CanonicalMemory) -> MemorySummary:
    return memory_to_summary(memory)


def retrieval_item_to_summary(item: RetrievalItem) -> RetrievalItemSummary:
    return RetrievalItemSummary(
        retrieval_id=item.retrieval_id,
        memory_version_id=item.memory_version_id,
        graph_edge_id=item.graph_edge_id,
        source_type=item.source_type,
        original_rank=item.original_rank,
        final_rank=item.final_rank,
        lexical_score=item.lexical_score,
        semantic_score=item.semantic_score,
        graph_score=item.graph_score,
        usefulness_score=item.usefulness_score,
        selected_for_context=item.selected_for_context,
        token_count=item.token_count,
    )


async def to_retrieved_memory(
    *,
    memory: CanonicalMemory,
    store: MemoryStore,
    token_counter: TokenCounter,
    selected: bool,
) -> RetrievedMemory:
    sources = await store.list_memory_sources(memory.version.id)
    return RetrievedMemory(
        memory_id=memory.identity.id,
        memory_version_id=memory.version.id,
        type=memory.identity.type,
        subject=memory.identity.subject,
        key=memory.identity.key,
        content=memory.version.content,
        status=memory.version.status,
        criticality=memory.version.criticality,
        confidence=memory.version.confidence,
        importance=memory.version.importance,
        usefulness_score=memory.version.usefulness_score,
        token_count=token_counter.count(memory.version.content),
        source_types=[],
        selected_for_context=selected,
        provenance_episode_ids=[source.episode_id for source in sources],
        explanation={"scope": asdict(memory.identity.scope)},
    )


def build_graph_neighborhood_response(
    paths: list[GraphPath],
    *,
    project_id: str | None,
) -> GraphNeighborhoodResponse:
    nodes: list[GraphNodeSummary] = []
    edges: list[GraphEdgeSummary] = []
    seen_nodes: set[str] = set()
    seen_edges: set[str] = set()
    for path in paths:
        for node in path.nodes:
            if node.uid in seen_nodes:
                continue
            seen_nodes.add(node.uid)
            nodes.append(
                GraphNodeSummary(
                    id=node.uid,
                    namespace_id=node.namespace_id,
                    node_type=node.node_type,
                    canonical_name=node.canonical_name,
                    normalized_name=node.normalized_name,
                    aliases=list(node.aliases),
                    metadata={},
                    project_id=project_id,
                )
            )
        for edge in path.edges:
            if edge.uid in seen_edges:
                continue
            seen_edges.add(edge.uid)
            edges.append(
                GraphEdgeSummary(
                    id=edge.uid,
                    source_node_id=edge.source_uid,
                    target_node_id=edge.target_uid,
                    relation=edge.relation,
                    source_memory_version_id=edge.source_memory_version_id,
                    status=edge.status,
                    confidence=edge.confidence,
                    usefulness_score=edge.usefulness_score,
                    valid_from=edge.valid_from,
                    valid_until=edge.valid_until,
                )
            )
    return GraphNeighborhoodResponse(nodes=nodes, edges=edges)


__all__ = [
    "build_graph_neighborhood_response",
    "memory_to_summary",
    "retrieval_item_to_summary",
    "to_job_summary",
    "to_memory_summary",
    "to_retrieved_memory",
]
