from dataclasses import dataclass, field

from memrise.ports.providers import (
    CompletionProvider,
    ConsolidationResult,
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
    captured: list[tuple[str, dict[str, object]]] = field(default_factory=list)
    consolidation_calls: list[dict[str, object]] = field(default_factory=list)

    async def extract_memories(self, *, text: str, context: dict[str, object]) -> ExtractionResult:
        self.captured.append((text, context))
        return self.result

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


MOCK_EMBEDDING_MODEL = "mock-embedding"


@dataclass
class MockEmbeddingProvider(EmbeddingProvider):
    vector: list[float] = field(default_factory=lambda: [0.1, 0.2, 0.3])

    async def embed(self, text: str) -> EmbeddingVector:
        del text
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
