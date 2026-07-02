from dataclasses import dataclass, field

from memrise.ports.providers import (
    CompletionProvider,
    EmbeddingProvider,
    ExtractedMemoryCandidate,
    ExtractionResult,
)


@dataclass
class MockCompletionProvider(CompletionProvider):
    result: ExtractionResult
    captured: list[tuple[str, dict[str, object]]] = field(default_factory=list)

    async def extract_memories(self, *, text: str, context: dict[str, object]) -> ExtractionResult:
        self.captured.append((text, context))
        return self.result


@dataclass
class MockEmbeddingProvider(EmbeddingProvider):
    vector: list[float] = field(default_factory=lambda: [0.1, 0.2, 0.3])

    async def embed(self, text: str) -> list[float]:
        del text
        return list(self.vector)


def single_candidate_result(candidate: ExtractedMemoryCandidate) -> ExtractionResult:
    return ExtractionResult(
        candidates=[candidate],
        model_name="mock",
        prompt_version="mock-v1",
    )
