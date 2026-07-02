from typing import Protocol

from pydantic import BaseModel, ConfigDict

from memrise.core.enums import Criticality, MemoryOperation, MemoryType


class ExtractedGraphRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    relation: str
    target: str


class ExtractedMemoryCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: MemoryType
    subject: str
    key: str
    content: str
    structured_value: dict[str, object]
    confidence: float
    importance: float
    criticality: Criticality
    operation_hint: MemoryOperation | None = None
    valid_until: str | None = None
    graph_relations: list[ExtractedGraphRelation] = []


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[ExtractedMemoryCandidate]
    model_name: str
    prompt_version: str


class CompletionProvider(Protocol):
    async def extract_memories(
        self, *, text: str, context: dict[str, object]
    ) -> ExtractionResult: ...


class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...


class TokenCounter(Protocol):
    def count(self, text: str) -> int: ...
