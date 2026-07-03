import pytest
from tests.mocks.graph_repository import GraphRepositoryStub
from tests.mocks.memory_store import MemoryStoreStub, make_memory
from tests.mocks.providers import MockEmbeddingProvider

from memrise.core.enums import MemoryStatus, RetrievalSourceType
from memrise.core.models import Scope
from memrise.ports.providers import EmbeddingVector
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


def test_lexical_score_and_scope_specificity() -> None:
    memory = make_memory(
        subject="Atlas",
        key="package_manager",
        content="Atlas uses pnpm for dependencies.",
        user_id="user-1",
        project_id="atlas",
    )

    assert lexical_score("Atlas pnpm dependencies", memory) > 0.5
    assert scope_specificity(memory) == 0.13


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
