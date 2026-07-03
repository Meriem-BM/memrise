from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from memrise.core.enums import (
    CandidateStageStatus,
    Criticality,
    EpisodeKind,
    FeedbackOutcome,
    FeedbackSource,
    JobStatus,
    JobType,
    MemoryStatus,
    MemoryType,
    RetrievalSourceType,
)
from memrise.core.time import require_utc

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class Scope:
    namespace_id: str
    agent_id: str
    user_id: str | None = None
    project_id: str | None = None

    def contains(self, other: Scope) -> bool:
        if self.namespace_id != other.namespace_id:
            return False
        if self.agent_id != other.agent_id:
            return False
        if self.user_id is not None and other.user_id != self.user_id:
            return False
        if self.project_id is not None and other.project_id != self.project_id:
            return False
        return True


@dataclass(frozen=True, slots=True)
class Episode:
    id: str
    namespace_id: str
    agent_id: str
    session_id: str
    kind: EpisodeKind
    content: str
    created_at: datetime
    user_id: str | None = None
    project_id: str | None = None
    metadata: JsonObject = field(default_factory=dict)
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        require_utc(self.created_at)


@dataclass(frozen=True, slots=True)
class EpisodeSaveOutcome:
    episode: Episode
    created: bool


@dataclass(frozen=True, slots=True)
class ApplyCandidateOutcome:
    memory: CanonicalMemory | None = None
    skip_reason: str | None = None


@dataclass(frozen=True, slots=True)
class MemoryIdentity:
    id: str
    namespace_id: str
    agent_id: str
    type: MemoryType
    subject: str
    key: str
    created_at: datetime
    user_id: str | None = None
    project_id: str | None = None

    def __post_init__(self) -> None:
        require_utc(self.created_at)

    @property
    def scope(self) -> Scope:
        return Scope(
            namespace_id=self.namespace_id,
            agent_id=self.agent_id,
            user_id=self.user_id,
            project_id=self.project_id,
        )


@dataclass(frozen=True, slots=True)
class MemoryVersion:
    id: str
    memory_id: str
    version_number: int
    content: str
    structured_value: JsonObject
    applicability: JsonObject
    status: MemoryStatus
    confidence: float
    importance: float
    criticality: Criticality
    usefulness_score: float
    valid_from: datetime
    created_at: datetime
    valid_until: datetime | None = None
    supersedes_version_id: str | None = None
    superseded_by_version_id: str | None = None
    embedding: list[float] | None = None

    def __post_init__(self) -> None:
        require_utc(self.valid_from)
        require_utc(self.created_at)
        if self.valid_until is not None:
            require_utc(self.valid_until)

    @property
    def is_lifecycle_active(self) -> bool:
        return self.status == MemoryStatus.ACTIVE


@dataclass(frozen=True, slots=True)
class CanonicalMemory:
    identity: MemoryIdentity
    version: MemoryVersion


@dataclass(frozen=True, slots=True)
class MemorySource:
    memory_version_id: str
    episode_id: str
    relation: str


@dataclass(frozen=True, slots=True)
class MemoryCandidateStage:
    id: str
    episode_id: str
    namespace_id: str
    agent_id: str
    candidate_index: int
    schema_version: str
    model_name: str
    prompt_version: str
    classification: JsonObject
    candidate: JsonObject
    status: CandidateStageStatus
    promotion_score: float
    created_at: datetime
    updated_at: datetime
    user_id: str | None = None
    project_id: str | None = None
    memory_type: str | None = None
    subject: str | None = None
    key: str | None = None
    evidence_quote: str | None = None
    rejection_reason: str | None = None
    memory_version_id: str | None = None

    def __post_init__(self) -> None:
        require_utc(self.created_at)
        require_utc(self.updated_at)


@dataclass(frozen=True, slots=True)
class RetrievalTrace:
    id: str
    namespace_id: str
    agent_id: str
    query: str
    token_budget: int
    created_at: datetime
    task_type: str | None = None
    project_id: str | None = None


@dataclass(frozen=True, slots=True)
class RetrievalItem:
    retrieval_id: str
    source_type: RetrievalSourceType
    original_rank: int
    final_rank: int
    usefulness_score: float
    selected_for_context: bool
    token_count: int
    memory_version_id: str | None = None
    graph_edge_id: str | None = None
    lexical_score: float | None = None
    semantic_score: float | None = None
    graph_score: float | None = None


@dataclass(frozen=True, slots=True)
class Feedback:
    id: str
    retrieval_id: str
    outcome: FeedbackOutcome
    source: FeedbackSource
    confidence: float
    created_at: datetime
    memory_version_id: str | None = None
    graph_edge_id: str | None = None
    task_type: str | None = None


@dataclass(frozen=True, slots=True)
class BackgroundJob:
    id: str
    type: JobType
    payload: JsonObject
    status: JobStatus
    attempts: int
    max_attempts: int
    run_at: datetime
    created_at: datetime
    updated_at: datetime
    locked_at: datetime | None = None
    locked_by: str | None = None
    last_error: str | None = None
