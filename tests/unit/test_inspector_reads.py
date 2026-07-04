from datetime import UTC, datetime, timedelta

from memrise.core.enums import CandidateStageStatus, EpisodeKind, MemoryStatus
from memrise.core.models import Episode, MemoryCandidateStage
from memrise.learning.policy import DefaultFeedbackPolicy
from memrise.runtime.memory import Memrise
from memrise.runtime.token_counter import ApproximateTokenCounter
from tests.mocks.graph_repository import GraphRepositoryStub
from tests.mocks.graph_services import build_graph_projection_service
from tests.mocks.graph_store import GraphClaimStoreStub
from tests.mocks.memory_store import MemoryStoreStub, make_memory
from tests.mocks.providers import (
    MockCompletionProvider,
    MockEmbeddingProvider,
    no_memory_result,
)

NOW = datetime(2026, 7, 3, tzinfo=UTC)


class JobQueueStub:
    async def enqueue(self, **kwargs: object) -> str:
        del kwargs
        return "job-1"

    async def find_job_id_by_dedupe_key(self, dedupe_key: str) -> str | None:
        del dedupe_key
        return None

    async def claim_next(self, *, worker_id: str):
        del worker_id
        return None

    async def get_job(self, job_id: str):
        del job_id
        return None

    async def complete(self, job_id: str) -> None:
        del job_id

    async def fail(self, job_id: str, error: str) -> None:
        del job_id, error


def _memrise(store: MemoryStoreStub) -> Memrise:
    graph_repository = GraphRepositoryStub(available=False)
    claim_store = GraphClaimStoreStub()
    return Memrise(
        store=store,
        jobs=JobQueueStub(),
        graph_repository=graph_repository,
        graph_projection=build_graph_projection_service(
            graph_repository=graph_repository, claim_store=claim_store
        ),
        graph_claim_store=claim_store,
        completion_provider=MockCompletionProvider(result=no_memory_result()),
        embedding_provider=MockEmbeddingProvider(),
        token_counter=ApproximateTokenCounter(),
        feedback_policy=DefaultFeedbackPolicy(),
    )


def _episode() -> Episode:
    return Episode(
        id="ep_1",
        namespace_id="ns",
        agent_id="agent",
        user_id="user",
        session_id="session-1",
        project_id="atlas",
        kind=EpisodeKind.USER_MESSAGE,
        content="Atlas uses pnpm.",
        created_at=NOW,
    )


def _stage() -> MemoryCandidateStage:
    return MemoryCandidateStage(
        id="cand_1",
        episode_id="ep_1",
        namespace_id="ns",
        agent_id="agent",
        candidate_index=0,
        schema_version="memory_extraction_v1",
        model_name="mock",
        prompt_version="memory_extraction_v1",
        classification={"durability": "durable", "sensitivity": "normal"},
        candidate={"content": "Atlas uses pnpm."},
        status=CandidateStageStatus.PROMOTED,
        promotion_score=0.81,
        memory_version_id="memv_1",
        subject="Atlas",
        key="package_manager",
        memory_type="decision",
        evidence_quote="Atlas uses pnpm.",
        created_at=NOW,
        updated_at=NOW,
    )


async def test_list_session_episodes_returns_summaries() -> None:
    store = MemoryStoreStub()
    store.episodes = {"ep_1": _episode()}
    memrise = _memrise(store)

    episodes = await memrise.list_session_episodes(
        namespace_id="ns", agent_id="agent", session_id="session-1"
    )

    assert len(episodes) == 1
    assert episodes[0].id == "ep_1"
    assert episodes[0].kind == EpisodeKind.USER_MESSAGE
    assert episodes[0].content == "Atlas uses pnpm."


async def test_list_episode_candidates_returns_stage_summaries() -> None:
    store = MemoryStoreStub()
    store.candidate_stages = {"cand_1": _stage()}
    store.memories = [make_memory(memory_id="mem_pm", version_id="memv_1")]
    memrise = _memrise(store)

    stages = await memrise.list_episode_candidates("ep_1")

    assert len(stages) == 1
    summary = stages[0]
    assert summary.status == CandidateStageStatus.PROMOTED
    assert summary.promotion_score == 0.81
    assert summary.memory_version_id == "memv_1"
    assert summary.memory_id == "mem_pm"
    assert summary.classification["durability"] == "durable"


async def test_list_episode_candidates_handles_missing_memory() -> None:
    store = MemoryStoreStub()
    store.candidate_stages = {"cand_1": _stage()}
    # No memories seeded: the stage's memory_version_id resolves to nothing.
    memrise = _memrise(store)

    stages = await memrise.list_episode_candidates("ep_1")

    assert len(stages) == 1
    assert stages[0].memory_id is None


async def test_run_lifecycle_returns_counts() -> None:
    store = MemoryStoreStub(
        memories=[
            make_memory(
                version_id="memv_due",
                valid_until=datetime.now(UTC) - timedelta(days=1),
            )
        ]
    )
    memrise = _memrise(store)

    result = await memrise.run_lifecycle()

    assert result.expired_memory_versions == 1
    assert result.decayed_versions >= 0
    assert result.resolved_contested == 0


async def test_list_memories_filters_contested() -> None:
    store = MemoryStoreStub(
        memories=[
            make_memory(memory_id="mem_a", version_id="memv_a", key="a"),
            make_memory(
                memory_id="mem_b",
                version_id="memv_b",
                key="b",
                status=MemoryStatus.CONTESTED,
            ),
        ]
    )
    memrise = _memrise(store)

    contested = await memrise.list_memories(
        namespace_id="ns",
        agent_id="agent",
        user_id="user",
        project_id="atlas",
        status=MemoryStatus.CONTESTED,
    )
    default = await memrise.list_memories(
        namespace_id="ns",
        agent_id="agent",
        user_id="user",
        project_id="atlas",
    )

    assert [memory.memory_id for memory in contested] == ["mem_b"]
    assert [memory.memory_id for memory in default] == ["mem_a"]
