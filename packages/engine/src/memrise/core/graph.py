from dataclasses import dataclass
from datetime import datetime

from memrise.core.enums import GraphClaimStatus, GraphEdgeStatus
from memrise.core.time import require_utc


@dataclass(frozen=True, slots=True)
class GraphNode:
    uid: str
    namespace_id: str
    node_type: str
    canonical_name: str
    normalized_name: str
    aliases: tuple[str, ...] = ()
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.created_at is not None:
            require_utc(self.created_at)


@dataclass(frozen=True, slots=True)
class GraphEdge:
    uid: str
    namespace_id: str
    source_uid: str
    target_uid: str
    relation: str
    source_memory_version_id: str
    status: GraphEdgeStatus
    confidence: float
    usefulness_score: float
    valid_from: datetime
    valid_until: datetime | None = None

    def __post_init__(self) -> None:
        require_utc(self.valid_from)
        if self.valid_until is not None:
            require_utc(self.valid_until)


@dataclass(frozen=True, slots=True)
class GraphPath:
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    source_memory_version_ids: tuple[str, ...]
    path_length: int
    path_confidence: float
    seed_match_score: float


@dataclass(frozen=True, slots=True)
class GraphNodeCandidate:
    temporary_id: str
    node_type: str
    name: str


@dataclass(frozen=True, slots=True)
class GraphEntity:
    id: str
    namespace_id: str
    core_type: str
    domain_type: str | None
    canonical_name: str
    normalized_name: str
    aliases: tuple[str, ...] = ()
    stable_source_id: str | None = None
    user_id: str | None = None
    project_id: str | None = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.created_at is not None:
            require_utc(self.created_at)


@dataclass(frozen=True, slots=True)
class GraphClaim:
    id: str
    namespace_id: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str
    supporting_memory_version_id: str
    evidence_text: str | None
    confidence: float
    usefulness_score: float
    status: GraphClaimStatus
    valid_from: datetime
    valid_until: datetime | None
    superseded_by_claim_id: str | None
    schema_version: str
    extractor_version: str | None
    extracted_at: datetime

    def __post_init__(self) -> None:
        require_utc(self.valid_from)
        require_utc(self.extracted_at)
        if self.valid_until is not None:
            require_utc(self.valid_until)


@dataclass(frozen=True, slots=True)
class GraphClaimPersistenceResult:
    memory_version_id: str
    namespace_id: str
    entities: tuple[GraphEntity, ...]
    claims: tuple[GraphClaim, ...]
    superseded_claim_count: int


@dataclass(frozen=True, slots=True)
class GraphRebuildResult:
    namespace_id: str
    projected_memory_version_count: int
    projected_claim_count: int


@dataclass(frozen=True, slots=True)
class GraphEdgeCandidate:
    source: str
    relation: str
    target: str
    claim_id: str | None = None
    usefulness_score: float = 0.5


@dataclass(frozen=True, slots=True)
class GraphProjection:
    memory_version_id: str
    namespace_id: str
    confidence: float
    valid_from: datetime
    supersedes_version_id: str | None
    nodes: tuple[GraphNodeCandidate, ...]
    edges: tuple[GraphEdgeCandidate, ...]

    def __post_init__(self) -> None:
        require_utc(self.valid_from)


@dataclass(frozen=True, slots=True)
class GraphProjectionResult:
    memory_version_id: str
    node_uids: tuple[str, ...]
    edge_uids: tuple[str, ...]
    superseded_edge_count: int


@dataclass(frozen=True, slots=True)
class GraphSearchRequest:
    namespace_id: str
    query: str
    depth: int = 1
    max_paths: int = 20
    max_nodes: int = 50


def clamp_graph_depth(depth: int, *, max_depth: int = 2) -> int:
    return max(1, min(depth, max_depth))
