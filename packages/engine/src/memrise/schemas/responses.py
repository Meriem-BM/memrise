from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from memrise.core.enums import (
    CandidateStageStatus,
    Criticality,
    EpisodeKind,
    GraphEdgeStatus,
    JobStatus,
    JobType,
    MemoryStatus,
    MemoryType,
    RetrievalSourceType,
)


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


class RememberResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory: MemorySummary
    source_episode_id: str | None = None


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


class RetrievalItemSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retrieval_id: str
    memory_version_id: str | None
    graph_edge_id: str | None
    source_type: RetrievalSourceType
    original_rank: int
    final_rank: int
    lexical_score: float | None
    semantic_score: float | None
    graph_score: float | None
    usefulness_score: float
    selected_for_context: bool
    token_count: int


class RetrievalDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retrieval_id: str
    items: list[RetrievalItemSummary]


class RetrievalTraceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    namespace_id: str
    agent_id: str
    query: str
    task_type: str | None
    project_id: str | None
    token_budget: int
    created_at: datetime


class GraphNodeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    namespace_id: str
    node_type: str
    canonical_name: str
    normalized_name: str
    aliases: list[str]
    metadata: dict[str, Any]
    project_id: str | None


class GraphEdgeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source_node_id: str
    target_node_id: str
    relation: str
    source_memory_version_id: str
    status: GraphEdgeStatus
    confidence: float
    usefulness_score: float
    valid_from: datetime
    valid_until: datetime | None


class GraphNeighborhoodResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[GraphNodeSummary]
    edges: list[GraphEdgeSummary]


class JobSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: JobType
    status: JobStatus
    attempts: int
    max_attempts: int
    run_at: datetime
    locked_at: datetime | None
    locked_by: str | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class EpisodeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    namespace_id: str
    agent_id: str
    session_id: str
    kind: EpisodeKind
    content: str
    user_id: str | None
    project_id: str | None
    created_at: datetime


class CandidateStageSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    episode_id: str
    candidate_index: int
    status: CandidateStageStatus
    promotion_score: float
    rejection_reason: str | None
    memory_version_id: str | None
    memory_id: str | None
    memory_type: str | None
    subject: str | None
    key: str | None
    evidence_quote: str | None
    classification: dict[str, Any]
    created_at: datetime


class LifecycleRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expired_memory_versions: int
    decayed_versions: int
    resolved_contested: int
    expired_claims: int
    expired_edges: int
