import json
from pathlib import Path
from time import perf_counter
from typing import TypedDict, cast

import pytest

from memrise.core.models import Scope
from memrise.ports.providers import EmbeddingProvider, EmbeddingVector
from memrise.read.evaluation import RetrievalObservation, evaluate_retrieval
from memrise.read.retrieval import RetrievalService
from memrise.runtime.ids import UuidGenerator
from memrise.runtime.token_counter import ApproximateTokenCounter
from tests.mocks.graph_repository import GraphRepositoryStub
from tests.mocks.memory_store import MemoryStoreStub, make_memory


class RetrievalCase(TypedDict):
    id: str
    subject: str
    key: str
    content: str
    queries: list[str]


CASES = cast(
    list[RetrievalCase],
    json.loads((Path(__file__).parent / "retrieval_cases.json").read_text(encoding="utf-8")),
)


class CorpusEmbeddingProvider(EmbeddingProvider):
    def __init__(self, cases: list[RetrievalCase]) -> None:
        self._query_index = {
            query: index for index, case in enumerate(cases) for query in case["queries"]
        }
        self._dimensions = len(cases)

    async def embed(self, text: str) -> EmbeddingVector:
        values = [0.0] * self._dimensions
        values[self._query_index[text]] = 1.0
        return EmbeddingVector(values=values, model="eval-embedding", dimensions=self._dimensions)

    async def embed_many(self, texts: list[str]) -> list[EmbeddingVector]:
        return [await self.embed(text) for text in texts]


@pytest.mark.asyncio
async def test_labeled_retrieval_corpus_quality() -> None:
    assert len(CASES) == 20
    assert sum(len(case["queries"]) for case in CASES) == 120
    dimensions = len(CASES)
    memories = []
    for index, case in enumerate(CASES):
        embedding = [0.0] * dimensions
        embedding[index] = 1.0
        memories.append(
            make_memory(
                memory_id=f"mem_{case['id']}",
                version_id=f"memv_{case['id']}",
                subject=case["subject"],
                key=case["key"],
                content=case["content"],
                embedding=embedding,
                embedding_model="eval-embedding",
            )
        )
    store = MemoryStoreStub(memories=memories)
    service = RetrievalService(
        store=store,
        graph_repository=GraphRepositoryStub(available=False),
        embedding_provider=CorpusEmbeddingProvider(CASES),
        token_counter=ApproximateTokenCounter(),
        ids=UuidGenerator(),
    )
    scope = Scope(namespace_id="ns", agent_id="agent", user_id="user", project_id="atlas")
    observations = []
    for case in CASES:
        for query_index, query in enumerate(case["queries"]):
            started = perf_counter()
            _, _, ranked, _, _ = await service.retrieve(
                scope=scope,
                query=query,
                task_type=None,
                token_budget=2_000,
                limit=10,
                graph_hops=1,
            )
            observations.append(
                RetrievalObservation(
                    query_id=f"{case['id']}:{query_index}",
                    relevant_ids=frozenset({f"memv_{case['id']}"}),
                    ranked_ids=tuple(memory.version.id for memory in ranked),
                    latency_ms=(perf_counter() - started) * 1_000,
                )
            )
    evaluation = evaluate_retrieval(observations, k=10)

    assert evaluation.query_count == 120
    assert evaluation.recall_at_k == 1.0
    assert evaluation.mrr >= 0.8
    assert evaluation.ndcg_at_k >= 0.85
