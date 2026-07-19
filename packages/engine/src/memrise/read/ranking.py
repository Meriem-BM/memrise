from dataclasses import dataclass, field

from memrise.core.enums import RetrievalSourceType

RRF_K = 60


@dataclass(frozen=True, slots=True)
class RankingConfig:
    """Retrieval relevance and bounded utility weights.

    RRF is normalized against the best possible score across enabled channels,
    so utility signals cannot overwhelm retrieval relevance simply because RRF
    uses small reciprocal values.
    """

    channel_weights: dict[RetrievalSourceType, float] = field(
        default_factory=lambda: {
            RetrievalSourceType.STRUCTURED: 1.25,
            RetrievalSourceType.LEXICAL: 1.15,
            RetrievalSourceType.SEMANTIC: 1.0,
            RetrievalSourceType.GRAPH: 1.0,
        }
    )
    usefulness_weight: float = 0.04
    confidence_weight: float = 0.03
    user_scope_boost: float = 0.01
    project_scope_boost: float = 0.02
    task_match_boost: float = 0.02
    contested_penalty: float = 0.02
    reranker_weight: float = 0.35
    reranker_candidate_limit: int = 30
    minimum_semantic_score: float = 0.2

    def __post_init__(self) -> None:
        if any(weight < 0 for weight in self.channel_weights.values()):
            raise ValueError("channel weights must be non-negative")
        bounded_values = (
            self.usefulness_weight,
            self.confidence_weight,
            self.user_scope_boost,
            self.project_scope_boost,
            self.task_match_boost,
            self.contested_penalty,
            self.reranker_weight,
            self.minimum_semantic_score,
        )
        if any(value < 0 for value in bounded_values):
            raise ValueError("ranking weights and boosts must be non-negative")
        if self.reranker_weight > 1:
            raise ValueError("reranker_weight must be at most 1")
        if self.minimum_semantic_score > 1:
            raise ValueError("minimum_semantic_score must be at most 1")
        if self.reranker_candidate_limit < 1:
            raise ValueError("reranker_candidate_limit must be positive")

    @property
    def maximum_rrf_score(self) -> float:
        return sum(self.channel_weights.values()) / (RRF_K + 1)


def normalized_rrf_score(
    ranked_sources: list[tuple[RetrievalSourceType, int]],
    *,
    config: RankingConfig,
) -> float:
    maximum = config.maximum_rrf_score
    if maximum <= 0:
        return 0.0
    raw = sum(
        config.channel_weights.get(source_type, 0.0) / (RRF_K + rank)
        for source_type, rank in ranked_sources
    )
    return min(1.0, raw / maximum)
