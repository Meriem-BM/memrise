from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from memrise.core.enums import EpisodeKind, FeedbackOutcome, FeedbackSource


class CaptureEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: EpisodeKind
    content: str = Field(min_length=1, max_length=50_000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CaptureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    namespace_id: str = Field(min_length=1, max_length=128)
    agent_id: str = Field(min_length=1, max_length=128)
    session_id: str = Field(min_length=1, max_length=256)
    user_id: str | None = Field(default=None, max_length=256)
    project_id: str | None = Field(default=None, max_length=256)
    events: list[CaptureEvent] = Field(min_length=1, max_length=100)


class RetrieveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    namespace_id: str = Field(min_length=1, max_length=128)
    agent_id: str = Field(min_length=1, max_length=128)
    query: str = Field(min_length=1, max_length=20_000)
    user_id: str | None = Field(default=None, max_length=256)
    project_id: str | None = Field(default=None, max_length=256)
    task_type: str | None = Field(default=None, max_length=128)
    token_budget: int = Field(default=800, ge=64, le=32_000)
    limit: int = Field(default=10, ge=1, le=100)
    graph_hops: int = Field(default=1, ge=0, le=2)


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: FeedbackOutcome
    source: FeedbackSource
    memory_version_id: str | None = None
    graph_edge_id: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    task_type: str | None = None


class ConsolidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    namespace_id: str = Field(min_length=1, max_length=128)
    agent_id: str = Field(min_length=1, max_length=128)
    session_id: str = Field(min_length=1, max_length=256)
    user_id: str | None = Field(default=None, max_length=256)
    project_id: str | None = Field(default=None, max_length=256)
