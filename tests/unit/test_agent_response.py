from memrise.learning.policy import DefaultFeedbackPolicy
from memrise.ports.providers import AnswerResult
from memrise.runtime.memory import Memrise
from memrise.runtime.token_counter import ApproximateTokenCounter
from tests.mocks.graph_repository import GraphRepositoryStub
from tests.mocks.graph_services import build_graph_projection_service
from tests.mocks.graph_store import GraphClaimStoreStub
from tests.mocks.memory_store import MemoryStoreStub, make_memory
from tests.mocks.providers import MockCompletionProvider, MockEmbeddingProvider, no_memory_result


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


def _memrise(store: MemoryStoreStub, completion: MockCompletionProvider) -> Memrise:
    graph_repository = GraphRepositoryStub(available=False)
    claim_store = GraphClaimStoreStub()
    return Memrise(
        store=store,
        jobs=JobQueueStub(),
        graph_repository=graph_repository,
        graph_projection=build_graph_projection_service(
            graph_repository=graph_repository,
            claim_store=claim_store,
        ),
        graph_claim_store=claim_store,
        completion_provider=completion,
        embedding_provider=MockEmbeddingProvider(),
        token_counter=ApproximateTokenCounter(),
        feedback_policy=DefaultFeedbackPolicy(),
    )


async def test_respond_answers_with_retrieved_memory_context() -> None:
    store = MemoryStoreStub(
        memories=[
            make_memory(
                content="User identifies their name as Lina.",
                subject="Lina",
                key="user_name",
            )
        ]
    )
    completion = MockCompletionProvider(
        result=no_memory_result(),
        answer=AnswerResult(
            answer="Your name is Lina.",
            model_name="mock-qwen",
            prompt_version="agent_answer_v1",
        ),
    )
    memory = _memrise(store, completion)

    response = await memory.respond(
        namespace_id="ns",
        agent_id="agent",
        user_id="user",
        project_id="atlas",
        query="what's my name?",
    )

    assert response.answer == "Your name is Lina."
    assert response.model_name == "mock-qwen"
    assert response.memory_enabled is True
    assert response.retrieval is not None
    assert response.retrieval.memories[0].content == "User identifies their name as Lina."
    assert completion.answer_calls[0]["query"] == "what's my name?"
    assert "Lina" in str(completion.answer_calls[0]["context"])


async def test_respond_can_answer_without_memory_context() -> None:
    store = MemoryStoreStub(
        memories=[
            make_memory(
                content="User identifies their name as Lina.",
                subject="Lina",
                key="user_name",
            )
        ]
    )
    completion = MockCompletionProvider(
        result=no_memory_result(),
        answer=AnswerResult(
            answer="I do not know your name from this message.",
            model_name="mock-qwen",
            prompt_version="agent_answer_v1",
        ),
    )
    memory = _memrise(store, completion)

    response = await memory.respond(
        namespace_id="ns",
        agent_id="agent",
        user_id="user",
        project_id="atlas",
        query="what's my name?",
        use_memory=False,
    )

    assert response.answer == "I do not know your name from this message."
    assert response.memory_enabled is False
    assert response.retrieval is None
    assert completion.answer_calls[0]["query"] == "what's my name?"
    assert completion.answer_calls[0]["context"] == ""
    assert completion.answer_calls[0]["memories"] == []
