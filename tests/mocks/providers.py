from dataclasses import dataclass, field

from memrise.ports.providers import (
    AnswerResult,
    CompletionProvider,
    ConsolidationResult,
    DuplicateJudgementResult,
    DuplicateVerdict,
    EmbeddingProvider,
    EmbeddingVector,
    EpisodeClassification,
    EpisodeDurability,
    ExtractedMemoryCandidate,
    ExtractionResult,
    KnowledgeClass,
    Sensitivity,
)


def empty_consolidation_result() -> ConsolidationResult:
    return ConsolidationResult(
        candidates=[],
        model_name="mock",
        prompt_version="consolidation_v1",
    )


@dataclass
class MockCompletionProvider(CompletionProvider):
    result: ExtractionResult
    consolidation: ConsolidationResult = field(default_factory=empty_consolidation_result)
    answer: AnswerResult = field(
        default_factory=lambda: AnswerResult(
            answer="Mock answer from memory.",
            model_name="mock",
            prompt_version="agent_answer_v1",
        )
    )
    captured: list[tuple[str, dict[str, object]]] = field(default_factory=list)
    consolidation_calls: list[dict[str, object]] = field(default_factory=list)
    answer_calls: list[dict[str, object]] = field(default_factory=list)
    judge_calls: list[list[dict[str, object]]] = field(default_factory=list)
    # Pair (left_id, right_id) tuples the judge should report as equivalent.
    equivalent_pairs: set[tuple[str, str]] = field(default_factory=set)

    async def extract_memories(self, *, text: str, context: dict[str, object]) -> ExtractionResult:
        self.captured.append((text, context))
        return self.result

    async def judge_duplicate_pairs(
        self, *, pairs: list[dict[str, object]], context: dict[str, object]
    ) -> DuplicateJudgementResult:
        self.judge_calls.append(pairs)
        verdicts = [
            DuplicateVerdict(
                left_id=str(pair["left_id"]),
                right_id=str(pair["right_id"]),
                equivalent=(str(pair["left_id"]), str(pair["right_id"])) in self.equivalent_pairs,
            )
            for pair in pairs
        ]
        return DuplicateJudgementResult(
            verdicts=verdicts, model_name="mock", prompt_version="duplicate_judge_v1"
        )

    async def consolidate_memories(
        self,
        *,
        episodes: list[dict[str, object]],
        existing_memories: list[dict[str, object]],
        context: dict[str, object],
    ) -> ConsolidationResult:
        self.consolidation_calls.append(
            {
                "episodes": episodes,
                "existing_memories": existing_memories,
                "context": context,
            }
        )
        return self.consolidation

    async def answer_question(
        self,
        *,
        query: str,
        context: str,
        memories: list[dict[str, object]],
    ) -> AnswerResult:
        self.answer_calls.append(
            {
                "query": query,
                "context": context,
                "memories": memories,
            }
        )
        return self.answer


MOCK_EMBEDDING_MODEL = "mock-embedding"


@dataclass
class MockEmbeddingProvider(EmbeddingProvider):
    vector: list[float] = field(default_factory=lambda: [0.1, 0.2, 0.3])
    embed_calls: int = 0
    embed_many_calls: int = 0
    embedded_texts: list[str] = field(default_factory=list)

    async def embed(self, text: str) -> EmbeddingVector:
        self.embed_calls += 1
        self.embedded_texts.append(text)
        return self._vector()

    async def embed_many(self, texts: list[str]) -> list[EmbeddingVector]:
        self.embed_many_calls += 1
        self.embedded_texts.extend(texts)
        return [self._vector() for _ in texts]

    def _vector(self) -> EmbeddingVector:
        return EmbeddingVector(
            values=list(self.vector),
            model=MOCK_EMBEDDING_MODEL,
            dimensions=len(self.vector),
        )


def single_candidate_result(candidate: ExtractedMemoryCandidate) -> ExtractionResult:
    return ExtractionResult(
        classification=EpisodeClassification(
            should_extract=True,
            durability=EpisodeDurability.DURABLE,
            knowledge_classes=[KnowledgeClass(candidate.type.value)],
            reason_codes=["test_candidate"],
            sensitivity=Sensitivity.NORMAL,
        ),
        candidates=[candidate],
        model_name="mock",
        prompt_version="memory_extraction_v1",
    )


def no_memory_result(reason: str = "noise") -> ExtractionResult:
    return ExtractionResult(
        classification=EpisodeClassification(
            should_extract=False,
            durability=EpisodeDurability.NONE,
            knowledge_classes=[KnowledgeClass.NOISE],
            reason_codes=[reason],
            sensitivity=Sensitivity.NORMAL,
        ),
        candidates=[],
        model_name="mock",
        prompt_version="memory_extraction_v1",
    )
