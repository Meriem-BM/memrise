from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from memrise.core.enums import Criticality, MemoryStatus, MemoryType, RetrievalSourceType


class CaptureResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    episode_ids: list[str]
    job_ids: list[str]


class RetrievedMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_id: str
    memory_version_id: str
    type: MemoryType
    subject: str
    key: str
    content: str
    status: MemoryStatus
    criticality: Criticality
    confidence: float
    importance: float
    usefulness_score: float
    token_count: int
    source_types: list[RetrievalSourceType]
    selected_for_context: bool
    provenance_episode_ids: list[str]
    explanation: dict[str, Any]


class RetrieveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retrieval_id: str
    query: str
    token_budget: int
    used_tokens: int
    critical: list[RetrievedMemory]
    memories: list[RetrievedMemory]
    context: str


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback_id: str
    updated_memory_version_id: str | None
    updated_graph_edge_id: str | None
    usefulness_score: float | None


class ConsolidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    accepted: bool


class MemorySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_id: str
    memory_version_id: str
    type: MemoryType
    subject: str
    key: str
    content: str
    status: MemoryStatus
    criticality: Criticality
    usefulness_score: float
    created_at: datetime
    valid_until: datetime | None


class MemoryExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_id: str
    current_version: MemorySummary | None
    versions: list[MemorySummary]
    provenance_episode_ids: list[str]
    graph_edges: list[dict[str, Any]]
    retrieval_feedback: list[dict[str, Any]]
