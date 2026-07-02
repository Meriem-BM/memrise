from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

from memrise.core.enums import Criticality, MemoryStatus, RetrievalSourceType
from memrise.core.models import CanonicalMemory, RetrievalItem, RetrievalTrace, Scope
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


def reciprocal_rank_fusion(candidates: list[RetrievalCandidate]) -> dict[str, float]:
    scores: dict[str, float] = defaultdict(float)
    for candidate in candidates:
        scores[candidate.memory.version.id] += 1.0 / (RRF_K + candidate.rank)
    return dict(scores)


def _terms(text: str) -> set[str]:
    return {part.strip(".,:;!?()[]{}\"'").lower() for part in text.split() if part.strip()}


def lexical_score(query: str, memory: CanonicalMemory) -> float:
    query_terms = _terms(query)
    content_terms = _terms(
        f"{memory.identity.subject} {memory.identity.key} {memory.version.content}"
    )
    if not query_terms:
        return 0.0
    return len(query_terms & content_terms) / len(query_terms)


def scope_specificity(memory: CanonicalMemory) -> float:
    score = 0.0
    if memory.identity.user_id is not None:
        score += 0.05
    if memory.identity.project_id is not None:
        score += 0.08
    return score


class RetrievalService:
    def __init__(
        self,
        *,
        store: MemoryStore,
        embedding_provider: EmbeddingProvider,
        token_counter: TokenCounter,
        ids: IdGenerator,
    ) -> None:
        self._store = store
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
        critical = self._select_critical(applicable, query, token_budget)

        normal_pool = [
            memory
            for memory in applicable
            if memory.version.criticality != Criticality.MUST_INCLUDE
        ]
        lexical = sorted(
            [
                RetrievalCandidate(
                    memory, RetrievalSourceType.LEXICAL, index + 1, lexical_score(query, memory)
                )
                for index, memory in enumerate(normal_pool)
            ],
            key=lambda item: item.score,
            reverse=True,
        )
        structured = sorted(
            [
                RetrievalCandidate(
                    memory,
                    RetrievalSourceType.STRUCTURED,
                    index + 1,
                    lexical_score(f"{memory.identity.subject} {memory.identity.key}", memory),
                )
                for index, memory in enumerate(normal_pool)
            ],
            key=lambda item: item.score,
            reverse=True,
        )
        await self._embedding_provider.embed(query)
        semantic = [
            RetrievalCandidate(
                memory, RetrievalSourceType.SEMANTIC, index + 1, memory.version.importance
            )
            for index, memory in enumerate(normal_pool)
        ]
        graph_nodes, graph_edges = await self._store.list_graph_neighborhood(
            scope=scope,
            query=query,
            hops=graph_hops,
        )
        del graph_nodes
        graph_version_ids = {edge.source_memory_version_id for edge in graph_edges}
        graph = [
            RetrievalCandidate(memory, RetrievalSourceType.GRAPH, index + 1, 0.6)
            for index, memory in enumerate(normal_pool)
            if memory.version.id in graph_version_ids
        ]

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
            created_at=datetime.now(UTC),
        )
        items: list[RetrievalItem] = []
        for rank, memory in enumerate(ranked, start=1):
            items.append(
                RetrievalItem(
                    retrieval_id=retrieval_id,
                    memory_version_id=memory.version.id,
                    source_type=RetrievalSourceType.LEXICAL,
                    original_rank=rank,
                    final_rank=rank,
                    lexical_score=lexical_score(query, memory),
                    usefulness_score=memory.version.usefulness_score,
                    selected_for_context=memory.version.id in selected_ids,
                    token_count=self._token_counter.count(memory.version.content),
                )
            )
        await self._store.save_retrieval_trace(trace, items)
        context_parts = [memory.version.content for memory in selected]
        context = "\n".join(f"- {part}" for part in context_parts)
        used_tokens = self._token_counter.count(context)
        selected_critical = [memory for memory in critical if memory.version.id in selected_ids]
        selected_normal = [
            memory for memory in selected if memory.version.criticality != Criticality.MUST_INCLUDE
        ]
        return retrieval_id, selected_critical, selected_normal, context, used_tokens

    def _is_applicable(self, memory: CanonicalMemory) -> bool:
        version = memory.version
        return version.status == MemoryStatus.ACTIVE

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
