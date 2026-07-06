"""Golden-set evaluation: capture -> extract -> reconcile -> retrieve, end to end.

Extraction results are scripted per episode (no LLM calls), so this suite pins
the deterministic pipeline around the model: the extraction gate, validation,
reconciliation, near-duplicate detection, ranking, and task-type applicability.
Add a case to golden_cases.json whenever a memory-quality bug is fixed.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from memrise.core.enums import JobStatus, JobType, MemoryStatus
from memrise.core.models import BackgroundJob
from memrise.learning.policy import DefaultFeedbackPolicy
from memrise.ports.providers import (
    AnswerResult,
    ConsolidationResult,
    DuplicateJudgementResult,
    EpisodeDurability,
    ExtractionResult,
    Sensitivity,
)
from memrise.runtime.memory import Memrise
from memrise.runtime.token_counter import ApproximateTokenCounter
from tests.mocks.graph_repository import GraphRepositoryStub
from tests.mocks.graph_services import build_graph_projection_service
from tests.mocks.graph_store import GraphClaimStoreStub
from tests.mocks.memory_store import MemoryStoreStub
from tests.mocks.providers import MockEmbeddingProvider

CASES = json.loads((Path(__file__).parent / "golden_cases.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 7, 3, tzinfo=UTC)


def _extraction_result(spec: dict[str, Any]) -> ExtractionResult:
    classification = spec.get("classification", {})
    return ExtractionResult.model_validate(
        {
            "classification": {
                "should_extract": classification.get("should_extract", True),
                "durability": classification.get("durability", EpisodeDurability.DURABLE.value),
                "sensitivity": classification.get("sensitivity", Sensitivity.NORMAL.value),
            },
            "candidates": spec.get("candidates", []),
            "model_name": "golden",
            "prompt_version": "memory_extraction_v1",
        }
    )


@dataclass
class ScriptedCompletionProvider:
    results_by_text: dict[str, ExtractionResult]

    async def extract_memories(self, *, text: str, context: dict[str, object]) -> ExtractionResult:
        del context
        return self.results_by_text[text]

    async def judge_duplicate_pairs(
        self, *, pairs: list[dict[str, object]], context: dict[str, object]
    ) -> DuplicateJudgementResult:
        del pairs, context
        return DuplicateJudgementResult(
            verdicts=[], model_name="golden", prompt_version="duplicate_judge_v1"
        )

    async def consolidate_memories(
        self,
        *,
        episodes: list[dict[str, object]],
        existing_memories: list[dict[str, object]],
        context: dict[str, object],
    ) -> ConsolidationResult:
        del episodes, existing_memories, context
        return ConsolidationResult(
            candidates=[], model_name="golden", prompt_version="consolidation_v1"
        )

    async def answer_question(
        self,
        *,
        query: str,
        context: str,
        memories: list[dict[str, object]],
    ) -> AnswerResult:
        del query, context, memories
        return AnswerResult(
            answer="golden answer",
            model_name="golden",
            prompt_version="agent_answer_v1",
        )


@dataclass
class RecordingJobQueue:
    pending: list[BackgroundJob] = field(default_factory=list)
    counter: int = 0

    async def enqueue(
        self,
        *,
        job_type: JobType,
        payload: dict[str, object],
        dedupe_key: str | None = None,
    ) -> str:
        del dedupe_key
        self.counter += 1
        job = BackgroundJob(
            id=f"job_{self.counter}",
            type=job_type,
            payload=dict(payload),
            status=JobStatus.PENDING,
            attempts=0,
            max_attempts=3,
            run_at=NOW,
            created_at=NOW,
            updated_at=NOW,
        )
        self.pending.append(job)
        return job.id

    async def find_job_id_by_dedupe_key(self, dedupe_key: str) -> str | None:
        del dedupe_key
        return None

    async def claim_next(self, *, worker_id: str) -> BackgroundJob | None:
        del worker_id
        return self.pending.pop(0) if self.pending else None

    async def get_job(self, job_id: str) -> BackgroundJob | None:
        del job_id
        return None

    async def complete(self, job_id: str) -> None:
        del job_id

    async def fail(self, job_id: str, error: str) -> None:
        del job_id, error


def _build_memrise(case: dict[str, Any]) -> tuple[Memrise, MemoryStoreStub, RecordingJobQueue]:
    store = MemoryStoreStub()
    jobs = RecordingJobQueue()
    provider = ScriptedCompletionProvider(
        results_by_text={
            episode["content"]: _extraction_result(episode["extraction"])
            for episode in case["episodes"]
        }
    )
    graph_repository = GraphRepositoryStub(available=False)
    claim_store = GraphClaimStoreStub()
    memrise = Memrise(
        store=store,
        jobs=jobs,
        graph_repository=graph_repository,
        graph_projection=build_graph_projection_service(
            graph_repository=graph_repository, claim_store=claim_store
        ),
        graph_claim_store=claim_store,
        completion_provider=provider,
        embedding_provider=MockEmbeddingProvider(),
        token_counter=ApproximateTokenCounter(),
        feedback_policy=DefaultFeedbackPolicy(),
    )
    return memrise, store, jobs


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
async def test_golden_case(case: dict[str, Any]) -> None:
    memrise, store, jobs = _build_memrise(case)

    for episode in case["episodes"]:
        await memrise.capture(
            namespace_id="ns",
            agent_id="agent",
            session_id="golden-session",
            user_id="user",
            project_id="atlas",
            events=[{"kind": "user_message", "content": episode["content"]}],
        )
        while jobs.pending:
            processed = await memrise.process_job_once(worker_id="golden-worker")
            assert processed

    active = [memory for memory in store.memories if memory.version.status == MemoryStatus.ACTIVE]
    assert len(active) == case["expected_active_memories"], (
        f"{case['name']}: expected {case['expected_active_memories']} active memories, "
        f"got {[memory.version.content for memory in active]}"
    )

    for query_spec in case["queries"]:
        response = await memrise.retrieve(
            namespace_id="ns",
            agent_id="agent",
            query=query_spec["query"],
            user_id="user",
            project_id="atlas",
            task_type=query_spec.get("task_type"),
        )
        retrieved = [item.content for item in [*response.critical, *response.memories]]
        if "expect_top_contains" in query_spec:
            assert retrieved, f"{case['name']}: nothing retrieved for {query_spec['query']!r}"
            assert query_spec["expect_top_contains"].lower() in retrieved[0].lower(), (
                f"{case['name']}: top result {retrieved[0]!r} does not contain "
                f"{query_spec['expect_top_contains']!r}"
            )
        if "expect_absent" in query_spec:
            assert all(
                query_spec["expect_absent"].lower() not in content.lower() for content in retrieved
            ), f"{case['name']}: {query_spec['expect_absent']!r} leaked into {retrieved!r}"
