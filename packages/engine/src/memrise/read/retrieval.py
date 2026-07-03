from collections import defaultdict
from dataclasses import dataclass
from math import sqrt

from memrise.core.enums import Criticality, MemoryStatus, RetrievalSourceType
from memrise.core.graph import GraphSearchRequest, clamp_graph_depth
from memrise.core.models import CanonicalMemory, RetrievalItem, RetrievalTrace, Scope
from memrise.core.time import utc_now
from memrise.graph.retrieval import GraphTraversalService, should_use_graph_retrieval
from memrise.ports.graph_repository import GraphRepository
from memrise.ports.graph_store import GraphClaimStore
from memrise.ports.ids import IdGenerator
from memrise.ports.providers import EmbeddingProvider, TokenCounter
from memrise.ports.repositories import MemoryStore

RRF_K = 60


@dataclass(frozen=True, slots=True)
class RetrievalCandidate:
    memory: CanonicalMemory
    source_type: RetrievalSourceType
    rank: int
    score: float
    graph_edge_id: str | None = None


def reciprocal_rank_fusion(candidates: list[RetrievalCandidate]) -> dict[str, float]:
    scores: dict[str, float] = defaultdict(float)
    for candidate in candidates:
        scores[candidate.memory.version.id] += 1.0 / (RRF_K + candidate.rank)
    return dict(scores)


def _terms(text: str) -> set[str]:
    return {part.strip(".,:;!?()[]{}\"'").lower() for part in text.split() if part.strip()}


def _term_overlap(query: str, text: str) -> float:
    query_terms = _terms(query)
    if not query_terms:
        return 0.0
    return len(query_terms & _terms(text)) / len(query_terms)


def lexical_score(query: str, memory: CanonicalMemory) -> float:
    return _term_overlap(
        query, f"{memory.identity.subject} {memory.identity.key} {memory.version.content}"
    )


def structured_score(query: str, memory: CanonicalMemory) -> float:
    return _term_overlap(query, f"{memory.identity.subject} {memory.identity.key}")


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sqrt(sum(x * x for x in a))
    norm_b = sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def scope_specificity(memory: CanonicalMemory) -> float:
    score = 0.0
    if memory.identity.user_id is not None:
        score += 0.05
    if memory.identity.project_id is not None:
        score += 0.08
    return score


def graph_score(*, seed_match_score: float, path_confidence: float, path_length: int) -> float:
    depth_penalty = 1.0 if path_length <= 1 else 0.8
    return seed_match_score * path_confidence * depth_penalty


def _ranked_candidates(
    memories: list[CanonicalMemory],
    *,
    source_type: RetrievalSourceType,
    score_by_version_id: dict[str, float],
) -> list[RetrievalCandidate]:
    ordered = sorted(
        memories,
        key=lambda memory: score_by_version_id.get(memory.version.id, 0.0),
        reverse=True,
    )
    return [
        RetrievalCandidate(
            memory,
            source_type,
            rank,
            score_by_version_id.get(memory.version.id, 0.0),
        )
        for rank, memory in enumerate(ordered, start=1)
    ]


class RetrievalService:
    def __init__(
        self,
        *,
        store: MemoryStore,
        graph_repository: GraphRepository,
        graph_claim_store: GraphClaimStore | None = None,
        embedding_provider: EmbeddingProvider,
        token_counter: TokenCounter,
        ids: IdGenerator,
    ) -> None:
        self._store = store
        self._graph_repository = graph_repository
        self._graph_traversal = (
            GraphTraversalService(
                graph_repository=graph_repository,
                claim_store=graph_claim_store,
            )
            if graph_claim_store is not None
            else None
        )
        self._embedding_provider = embedding_provider
        self._token_counter = token_counter
        self._ids = ids

    async def retrieve(
        self,
        *,
        scope: Scope,
        query: str,
        task_type: str | None,
        token_budget: int,
        limit: int,
        graph_hops: int,
    ) -> tuple[str, list[CanonicalMemory], list[CanonicalMemory], str, int]:
        memories = await self._store.list_active_memories(scope=scope, include_contested=False)
        applicable = [memory for memory in memories if self._is_applicable(memory)]
        memory_by_version_id = {memory.version.id: memory for memory in applicable}
        critical = self._select_critical(applicable, query, token_budget)

        normal_pool = [
            memory
            for memory in applicable
            if memory.version.criticality != Criticality.MUST_INCLUDE
        ]

        lexical_scores = {memory.version.id: lexical_score(query, memory) for memory in normal_pool}
        structured_scores = {
            memory.version.id: structured_score(query, memory) for memory in normal_pool
        }
        semantic_scores = await self._semantic_scores(query, normal_pool)

        lexical = _ranked_candidates(
            normal_pool,
            source_type=RetrievalSourceType.LEXICAL,
            score_by_version_id=lexical_scores,
        )
        structured = _ranked_candidates(
            normal_pool,
            source_type=RetrievalSourceType.STRUCTURED,
            score_by_version_id=structured_scores,
        )
        semantic = _ranked_candidates(
            normal_pool,
            source_type=RetrievalSourceType.SEMANTIC,
            score_by_version_id=semantic_scores,
        )
        graph = await self._graph_candidates(
            scope=scope,
            query=query,
            graph_hops=graph_hops,
            memory_by_version_id=memory_by_version_id,
        )

        fused_scores = reciprocal_rank_fusion(lexical + structured + semantic + graph)
        ranked = sorted(
            normal_pool,
            key=lambda memory: (
                fused_scores.get(memory.version.id, 0.0)
                + memory.version.usefulness_score * 0.12
                + memory.version.confidence * 0.08
                + scope_specificity(memory)
            ),
            reverse=True,
        )
        selected = self._pack(critical, ranked[:limit], token_budget)
        selected_ids = {memory.version.id for memory in selected}
        retrieval_id = self._ids.new_id("retrieval")
        trace = RetrievalTrace(
            id=retrieval_id,
            namespace_id=scope.namespace_id,
            agent_id=scope.agent_id,
            query=query,
            task_type=task_type,
            project_id=scope.project_id,
            token_budget=token_budget,
            created_at=utc_now(),
        )
        best_source = _best_source_by_version(lexical + structured + semantic + graph)
        items: list[RetrievalItem] = []
        for rank, memory in enumerate(ranked, start=1):
            candidate = best_source.get(memory.version.id)
            is_graph = candidate is not None and candidate.source_type == RetrievalSourceType.GRAPH
            items.append(
                RetrievalItem(
                    retrieval_id=retrieval_id,
                    memory_version_id=memory.version.id,
                    graph_edge_id=candidate.graph_edge_id if candidate is not None else None,
                    source_type=(
                        candidate.source_type
                        if candidate is not None
                        else RetrievalSourceType.LEXICAL
                    ),
                    original_rank=rank,
                    final_rank=rank,
                    lexical_score=lexical_scores.get(memory.version.id),
                    semantic_score=semantic_scores.get(memory.version.id),
                    graph_score=candidate.score if is_graph and candidate is not None else None,
                    usefulness_score=memory.version.usefulness_score,
                    selected_for_context=memory.version.id in selected_ids,
                    token_count=self._token_counter.count(memory.version.content),
                )
            )
        await self._store.save_retrieval_trace(trace, items)
        context = "\n".join(f"- {memory.version.content}" for memory in selected)
        used_tokens = self._token_counter.count(context)
        selected_critical = [memory for memory in critical if memory.version.id in selected_ids]
        selected_normal = [
            memory for memory in selected if memory.version.criticality != Criticality.MUST_INCLUDE
        ]
        return retrieval_id, selected_critical, selected_normal, context, used_tokens

    async def _semantic_scores(
        self,
        query: str,
        memories: list[CanonicalMemory],
    ) -> dict[str, float]:
        with_embeddings = [memory for memory in memories if memory.version.embedding]
        if not with_embeddings:
            return {}
        query_embedding = await self._embedding_provider.embed(query)
        return {
            memory.version.id: cosine_similarity(query_embedding, memory.version.embedding or [])
            for memory in with_embeddings
        }

    async def _graph_candidates(
        self,
        *,
        scope: Scope,
        query: str,
        graph_hops: int,
        memory_by_version_id: dict[str, CanonicalMemory],
    ) -> list[RetrievalCandidate]:
        if not should_use_graph_retrieval(query):
            return []
        if not await self._graph_repository.is_available():
            return []
        depth = clamp_graph_depth(graph_hops)
        if self._graph_traversal is not None:
            paths = await self._graph_traversal.traverse_for_query(
                namespace_id=scope.namespace_id,
                query=query,
                depth=depth,
                project_id=scope.project_id,
            )
        else:
            paths = await self._graph_repository.search(
                GraphSearchRequest(
                    namespace_id=scope.namespace_id,
                    query=query,
                    depth=depth,
                )
            )
        candidates: list[RetrievalCandidate] = []
        seen_versions: set[str] = set()
        for index, path in enumerate(paths, start=1):
            for memory_version_id in path.source_memory_version_ids:
                if memory_version_id in seen_versions:
                    continue
                memory = memory_by_version_id.get(memory_version_id)
                if memory is None:
                    continue
                candidates.append(
                    RetrievalCandidate(
                        memory,
                        RetrievalSourceType.GRAPH,
                        index,
                        graph_score(
                            seed_match_score=path.seed_match_score,
                            path_confidence=path.path_confidence,
                            path_length=path.path_length,
                        ),
                        graph_edge_id=path.edges[-1].uid if path.edges else None,
                    )
                )
                seen_versions.add(memory_version_id)
        return candidates

    def _is_applicable(self, memory: CanonicalMemory) -> bool:
        version = memory.version
        now = utc_now()
        if version.status != MemoryStatus.ACTIVE:
            return False
        if version.valid_from > now:
            return False
        if version.valid_until is not None and version.valid_until <= now:
            return False
        return True

    def _select_critical(
        self,
        memories: list[CanonicalMemory],
        query: str,
        token_budget: int,
    ) -> list[CanonicalMemory]:
        critical_budget = max(1, int(token_budget * 0.2))
        selected: list[CanonicalMemory] = []
        used = 0
        for memory in sorted(
            [item for item in memories if item.version.criticality == Criticality.MUST_INCLUDE],
            key=lambda item: lexical_score(query, item),
            reverse=True,
        ):
            cost = self._token_counter.count(memory.version.content)
            if len(selected) >= 3 or used + cost > critical_budget:
                break
            selected.append(memory)
            used += cost
        return selected

    def _pack(
        self,
        critical: list[CanonicalMemory],
        ranked: list[CanonicalMemory],
        token_budget: int,
    ) -> list[CanonicalMemory]:
        selected: list[CanonicalMemory] = []
        seen: set[str] = set()
        used = 0
        for memory in [*critical, *ranked]:
            if memory.version.id in seen:
                continue
            cost = self._token_counter.count(memory.version.content)
            if used + cost > token_budget:
                continue
            selected.append(memory)
            seen.add(memory.version.id)
            used += cost
        return selected


def _best_source_by_version(
    candidates: list[RetrievalCandidate],
) -> dict[str, RetrievalCandidate]:
    """Pick one attributable source per memory: graph wins, then the best rank."""
    best: dict[str, RetrievalCandidate] = {}
    for candidate in candidates:
        version_id = candidate.memory.version.id
        current = best.get(version_id)
        if current is None:
            best[version_id] = candidate
            continue
        if current.source_type == RetrievalSourceType.GRAPH:
            continue
        if candidate.source_type == RetrievalSourceType.GRAPH or candidate.rank < current.rank:
            best[version_id] = candidate
    return best
