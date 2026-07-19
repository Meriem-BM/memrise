import pytest

from memrise.core.enums import Criticality, MemoryStatus, RetrievalSourceType
from memrise.core.models import Scope
from memrise.ports.providers import (
    EmbeddingVector,
    RerankCandidate,
    Reranker,
    RerankResult,
)
from memrise.read.retrieval import (
    RetrievalCandidate,
    RetrievalService,
    graph_score,
    lexical_score,
    reciprocal_rank_fusion,
    scope_specificity,
)
from memrise.runtime.ids import UuidGenerator
from memrise.runtime.token_counter import ApproximateTokenCounter
from tests.mocks.graph_repository import GraphRepositoryStub
from tests.mocks.memory_store import MemoryStoreStub, make_memory
from tests.mocks.providers import MockEmbeddingProvider


class PreferSecondReranker(Reranker):
    async def rerank(
        self,
        *,
        query: str,
        candidates: list[RerankCandidate],
    ) -> RerankResult:
        del query
        ids = {candidate.memory_version_id for candidate in candidates}
        assert {"memv_first", "memv_second"} <= ids
        return RerankResult(
            ordered_memory_version_ids=["memv_second", "memv_first"],
            model_name="test-reranker",
        )


def test_reciprocal_rank_fusion_combines_ranks() -> None:
    memory_a = make_memory(version_id="memv_a", content="Atlas uses pnpm.")
    memory_b = make_memory(version_id="memv_b", content="Atlas uses npm.")
    candidates = [
        RetrievalCandidate(memory_a, RetrievalSourceType.LEXICAL, 1, 0.9),
        RetrievalCandidate(memory_b, RetrievalSourceType.SEMANTIC, 2, 0.7),
        RetrievalCandidate(memory_a, RetrievalSourceType.SEMANTIC, 1, 0.8),
    ]

    scores = reciprocal_rank_fusion(candidates)

    assert scores["memv_a"] > scores["memv_b"]
    assert 0 < scores["memv_a"] <= 1


def test_lexical_score_and_scope_specificity() -> None:
    memory = make_memory(
        subject="Atlas",
        key="package_manager",
        content="Atlas uses pnpm for dependencies.",
        user_id="user-1",
        project_id="atlas",
    )

    assert lexical_score("Atlas pnpm dependencies", memory) > 0.5
    assert scope_specificity(memory) == 0.03


def test_graph_score_applies_depth_penalty() -> None:
    shallow = graph_score(seed_match_score=1.0, path_confidence=0.8, path_length=1)
    deep = graph_score(seed_match_score=1.0, path_confidence=0.8, path_length=2)

    assert shallow == pytest.approx(0.8)
    assert deep == pytest.approx(0.64)


async def test_retrieval_service_persists_trace_and_context() -> None:
    store = MemoryStoreStub(
        memories=[
            make_memory(
                version_id="memv_pnpm",
                content="Atlas uses pnpm for dependencies.",
            )
        ]
    )
    service = RetrievalService(
        store=store,
        graph_repository=GraphRepositoryStub(available=False),
        embedding_provider=MockEmbeddingProvider(),
        token_counter=ApproximateTokenCounter(),
        ids=UuidGenerator(),
    )
    scope = Scope(namespace_id="ns", agent_id="agent", user_id="user", project_id="atlas")

    retrieval_id, critical, memories, context, used_tokens = await service.retrieve(
        scope=scope,
        query="How should I install Atlas dependencies?",
        task_type="dependency_install",
        token_budget=200,
        limit=5,
        graph_hops=1,
    )

    assert retrieval_id.startswith("retrieval_")
    assert not critical
    assert memories
    assert "pnpm" in context
    assert used_tokens > 0
    assert retrieval_id in store.retrieval_traces
    assert store.retrieval_items[retrieval_id]


async def test_contested_memories_surface_with_rank_penalty() -> None:
    active = make_memory(
        memory_id="mem_active",
        version_id="memv_active",
        content="Atlas uses pnpm for dependencies.",
    )
    contested = make_memory(
        memory_id="mem_contested",
        version_id="memv_contested",
        key="package_manager_alt",
        content="Atlas uses pnpm for dependencies.",
        status=MemoryStatus.CONTESTED,
    )
    store = MemoryStoreStub(memories=[active, contested])
    service = RetrievalService(
        store=store,
        graph_repository=GraphRepositoryStub(available=False),
        embedding_provider=MockEmbeddingProvider(),
        token_counter=ApproximateTokenCounter(),
        ids=UuidGenerator(),
    )
    scope = Scope(namespace_id="ns", agent_id="agent", user_id="user", project_id="atlas")

    _, _, memories, _, _ = await service.retrieve(
        scope=scope,
        query="Atlas pnpm dependencies",
        task_type=None,
        token_budget=500,
        limit=5,
        graph_hops=1,
    )

    version_ids = [memory.version.id for memory in memories]
    assert "memv_contested" in version_ids
    assert version_ids.index("memv_active") < version_ids.index("memv_contested")


async def test_bounded_reranker_changes_precision_order() -> None:
    first = make_memory(
        memory_id="mem_first",
        version_id="memv_first",
        key="deploy_note",
        content="Atlas deploy documentation is available.",
    )
    second = make_memory(
        memory_id="mem_second",
        version_id="memv_second",
        key="deploy_day",
        content="Atlas deploys happen on Fridays.",
    )
    store = MemoryStoreStub(memories=[first, second])
    service = RetrievalService(
        store=store,
        graph_repository=GraphRepositoryStub(available=False),
        embedding_provider=MockEmbeddingProvider(),
        token_counter=ApproximateTokenCounter(),
        ids=UuidGenerator(),
        reranker=PreferSecondReranker(),
    )

    retrieval_id, _, memories, _, _ = await service.retrieve(
        scope=Scope(namespace_id="ns", agent_id="agent", user_id="user", project_id="atlas"),
        query="Atlas deploy",
        task_type=None,
        token_budget=500,
        limit=5,
        graph_hops=1,
    )

    assert [memory.version.id for memory in memories[:2]] == ["memv_second", "memv_first"]
    traces = {item.memory_version_id: item for item in store.retrieval_items[retrieval_id]}
    assert traces["memv_second"].original_rank != traces["memv_second"].final_rank


async def test_semantic_channel_only_compares_same_model_embeddings() -> None:
    store = MemoryStoreStub(
        memories=[
            make_memory(
                memory_id="mem_same",
                version_id="memv_same",
                key="k1",
                content="Atlas deploys on Fridays.",
                embedding=[0.1, 0.2, 0.3],
                embedding_model="mock-embedding",
            ),
            make_memory(
                memory_id="mem_other",
                version_id="memv_other",
                key="k2",
                content="Atlas deploys on Fridays too.",
                embedding=[0.1, 0.2, 0.3],
                embedding_model="legacy-model",
            ),
        ]
    )
    scope = Scope(namespace_id="ns", agent_id="agent", user_id="user", project_id="atlas")

    hits = await store.search_semantic(
        scope=scope,
        embedding=EmbeddingVector(values=[0.1, 0.2, 0.3], model="mock-embedding", dimensions=3),
        limit=10,
    )

    assert [memory.version.id for memory, _ in hits] == ["memv_same"]


async def test_lexical_channel_comes_from_store_search() -> None:
    store = MemoryStoreStub(
        memories=[
            make_memory(
                memory_id="mem_hit",
                version_id="memv_hit",
                content="Atlas uses pnpm for dependencies.",
            ),
            make_memory(
                memory_id="mem_miss",
                version_id="memv_miss",
                key="deploy_day",
                content="Deploys happen on Fridays.",
            ),
        ]
    )
    scope = Scope(namespace_id="ns", agent_id="agent", user_id="user", project_id="atlas")

    hits = await store.search_lexical(scope=scope, query="pnpm dependencies", limit=10)

    assert [memory.version.id for memory, _ in hits] == ["memv_hit"]


async def test_task_type_applicability_filters_and_boosts() -> None:
    deploy_only = make_memory(
        memory_id="mem_deploy",
        version_id="memv_deploy",
        key="deploy_rules",
        content="Atlas deploys need pnpm build first.",
        applicability={"task_type": "deploy"},
    )
    general = make_memory(
        memory_id="mem_general",
        version_id="memv_general",
        content="Atlas uses pnpm for dependencies.",
    )
    store = MemoryStoreStub(memories=[deploy_only, general])
    service = RetrievalService(
        store=store,
        graph_repository=GraphRepositoryStub(available=False),
        embedding_provider=MockEmbeddingProvider(),
        token_counter=ApproximateTokenCounter(),
        ids=UuidGenerator(),
    )
    scope = Scope(namespace_id="ns", agent_id="agent", user_id="user", project_id="atlas")

    _, _, for_review, _, _ = await service.retrieve(
        scope=scope,
        query="Atlas pnpm",
        task_type="code_review",
        token_budget=500,
        limit=5,
        graph_hops=1,
    )
    assert [memory.version.id for memory in for_review] == ["memv_general"]

    _, _, for_deploy, _, _ = await service.retrieve(
        scope=scope,
        query="Atlas pnpm",
        task_type="deploy",
        token_budget=500,
        limit=5,
        graph_hops=1,
    )
    deploy_ids = [memory.version.id for memory in for_deploy]
    assert deploy_ids[0] == "memv_deploy"
    assert "memv_general" in deploy_ids


async def test_retrieve_never_materializes_full_active_scope() -> None:
    critical = make_memory(
        memory_id="mem_rule",
        version_id="memv_rule",
        key="lockfile_rule",
        content="Never edit the Atlas lockfile manually.",
        criticality=Criticality.MUST_INCLUDE,
    )
    normal = make_memory(
        memory_id="mem_pm",
        version_id="memv_pm",
        content="Atlas uses pnpm for dependencies.",
    )
    store = MemoryStoreStub(memories=[critical, normal])

    async def forbidden(**_: object) -> list:
        raise AssertionError("retrieve must not call list_active_memories")

    store.list_active_memories = forbidden  # type: ignore[method-assign]
    service = RetrievalService(
        store=store,
        graph_repository=GraphRepositoryStub(available=False),
        embedding_provider=MockEmbeddingProvider(),
        token_counter=ApproximateTokenCounter(),
        ids=UuidGenerator(),
    )
    scope = Scope(namespace_id="ns", agent_id="agent", user_id="user", project_id="atlas")

    _, selected_critical, selected_normal, context, _ = await service.retrieve(
        scope=scope,
        query="Atlas pnpm lockfile",
        task_type=None,
        token_budget=500,
        limit=5,
        graph_hops=1,
    )

    assert [memory.version.id for memory in selected_critical] == ["memv_rule"]
    assert [memory.version.id for memory in selected_normal] == ["memv_pm"]
    assert "pnpm" in context
    assert "lockfile" in context


async def test_trace_only_persists_bounded_channel_candidates() -> None:
    relevant = make_memory(
        memory_id="mem_hit",
        version_id="memv_hit",
        content="Atlas uses pnpm for dependencies.",
    )
    unrelated = make_memory(
        memory_id="mem_noise",
        version_id="memv_noise",
        subject="weather",
        key="forecast",
        content="It rains in Lisbon in November.",
    )
    store = MemoryStoreStub(memories=[relevant, unrelated])
    service = RetrievalService(
        store=store,
        graph_repository=GraphRepositoryStub(available=False),
        embedding_provider=MockEmbeddingProvider(),
        token_counter=ApproximateTokenCounter(),
        ids=UuidGenerator(),
    )
    scope = Scope(namespace_id="ns", agent_id="agent", user_id="user", project_id="atlas")

    retrieval_id, _, _, _, _ = await service.retrieve(
        scope=scope,
        query="Atlas pnpm",
        task_type=None,
        token_budget=500,
        limit=5,
        graph_hops=1,
    )

    traced_ids = {item.memory_version_id for item in store.retrieval_items[retrieval_id]}
    assert "memv_hit" in traced_ids
    assert "memv_noise" not in traced_ids


async def test_retrieval_runs_channels_concurrently() -> None:
    import asyncio

    store = MemoryStoreStub(
        memories=[make_memory(version_id="memv_pnpm", content="Atlas uses pnpm.")]
    )
    # Barrier of 4 = the four store-backed channels (critical, structured, lexical,
    # semantic). If retrieval awaited them sequentially, the first would block on the
    # barrier forever and wait_for would time out. Reaching all 4 parties proves they
    # run concurrently.
    barrier = asyncio.Barrier(4)

    def gate(method):  # type: ignore[no-untyped-def]
        async def wrapped(*args, **kwargs):  # type: ignore[no-untyped-def]
            await barrier.wait()
            return await method(*args, **kwargs)

        return wrapped

    store.list_critical_memories = gate(store.list_critical_memories)  # type: ignore[method-assign]
    store.search_structured = gate(store.search_structured)  # type: ignore[method-assign]
    store.search_lexical = gate(store.search_lexical)  # type: ignore[method-assign]
    store.search_semantic = gate(store.search_semantic)  # type: ignore[method-assign]

    service = RetrievalService(
        store=store,
        graph_repository=GraphRepositoryStub(available=False),
        embedding_provider=MockEmbeddingProvider(),
        token_counter=ApproximateTokenCounter(),
        ids=UuidGenerator(),
    )
    scope = Scope(namespace_id="ns", agent_id="agent", user_id="user", project_id="atlas")

    retrieval_id, _, _, _, _ = await asyncio.wait_for(
        service.retrieve(
            scope=scope,
            query="Atlas pnpm",
            task_type=None,
            token_budget=200,
            limit=5,
            graph_hops=1,
        ),
        timeout=2.0,
    )
    assert retrieval_id.startswith("retrieval_")


async def test_retrieval_tolerates_channels_with_no_candidates() -> None:
    rule = make_memory(
        memory_id="mem_rule",
        version_id="memv_rule",
        key="lockfile_rule",
        content="Never edit the lockfile manually.",
        criticality=Criticality.MUST_INCLUDE,
    )
    store = MemoryStoreStub(memories=[rule])
    service = RetrievalService(
        store=store,
        graph_repository=GraphRepositoryStub(available=False),
        embedding_provider=MockEmbeddingProvider(),
        token_counter=ApproximateTokenCounter(),
        ids=UuidGenerator(),
    )
    scope = Scope(namespace_id="ns", agent_id="agent", user_id="user", project_id="atlas")

    # Lexical, structured, semantic, and graph all yield nothing for this query;
    # only the critical channel produces a memory. Retrieval must still succeed.
    _, critical, normal, context, used_tokens = await service.retrieve(
        scope=scope,
        query="totally unrelated weather question",
        task_type=None,
        token_budget=500,
        limit=5,
        graph_hops=1,
    )

    assert [memory.version.id for memory in critical] == ["memv_rule"]
    assert normal == []
    assert "lockfile" in context
    assert used_tokens > 0
