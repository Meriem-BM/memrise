from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from memrise.core.enums import Criticality, MemoryOperation, MemoryType


class EpisodeDurability(StrEnum):
    NONE = "none"
    SESSION = "session"
    TEMPORARY = "temporary"
    DURABLE = "durable"


class KnowledgeClass(StrEnum):
    PREFERENCE = "preference"
    FACT = "fact"
    DECISION = "decision"
    CONSTRAINT = "constraint"
    GOAL = "goal"
    LESSON = "lesson"
    CORRECTION = "correction"
    CONFLICT = "conflict"
    IDENTIFIER = "identifier"
    PROCEDURE = "procedure"
    NOISE = "noise"
    SENSITIVE = "sensitive"


class Sensitivity(StrEnum):
    NORMAL = "normal"
    POSSIBLE_SECRET = "possible_secret"
    SECRET = "secret"


class EvidenceRole(StrEnum):
    STATED = "stated"
    CORRECTED = "corrected"
    OBSERVED = "observed"
    INFERRED = "inferred"


class ExtractedGraphRelation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source: str = Field(min_length=1, max_length=256)
    relation: str = Field(min_length=1, max_length=64)
    target: str = Field(min_length=1, max_length=256)
    source_type: str | None = Field(
        default=None,
        max_length=64,
        description="Apache AGE node label, e.g. Person, Project, Technology.",
    )
    target_type: str | None = Field(
        default=None,
        max_length=64,
        description="Apache AGE node label, e.g. Person, Project, Technology.",
    )


class EpisodeClassification(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    should_extract: bool
    durability: EpisodeDurability
    knowledge_classes: list[KnowledgeClass] = Field(default_factory=list, max_length=16)
    reason_codes: list[str] = Field(default_factory=list, max_length=16)
    sensitivity: Sensitivity = Sensitivity.NORMAL


class ExtractedMemoryCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: MemoryType
    subject: str = Field(min_length=1, max_length=512)
    key: str = Field(min_length=1, max_length=512)
    content: str = Field(min_length=1, max_length=10_000)
    structured_value: dict[str, object] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    importance: float = Field(ge=0, le=1)
    criticality: Criticality
    operation_hint: MemoryOperation | None = None
    valid_until: str | None = Field(default=None, max_length=64)
    evidence_quote: str = Field(min_length=1, max_length=2_000)
    evidence_role: EvidenceRole = EvidenceRole.STATED
    applicability: dict[str, object] = Field(default_factory=dict)
    graph_relations: list[ExtractedGraphRelation] = Field(default_factory=list, max_length=20)
    search_text: str | None = Field(default=None, max_length=2_000)
    embedding_text: str | None = Field(default=None, max_length=2_000)

    @field_validator("valid_until")
    @classmethod
    def validate_valid_until(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(candidate)
        if parsed.tzinfo is None:
            msg = "valid_until must include a timezone"
            raise ValueError(msg)
        return parsed.astimezone(UTC).isoformat()


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="memory_extraction_v1")
    classification: EpisodeClassification
    candidates: list[ExtractedMemoryCandidate] = Field(default_factory=list, max_length=20)
    model_name: str
    prompt_version: str


class EmbeddingVector(BaseModel):
    """An embedding plus the model identity that produced it.

    Embeddings from different models are not comparable; every consumer must
    filter or guard on `model` before computing similarity.
    """

    model_config = ConfigDict(frozen=True)

    values: list[float]
    model: str
    dimensions: int


class CompletionProvider(Protocol):
    async def extract_memories(
        self, *, text: str, context: dict[str, object]
    ) -> ExtractionResult: ...


class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> EmbeddingVector: ...


class TokenCounter(Protocol):
    def count(self, text: str) -> int: ...
