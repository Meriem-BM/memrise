from dataclasses import dataclass
from math import log2
from statistics import mean


@dataclass(frozen=True, slots=True)
class RetrievalObservation:
    query_id: str
    relevant_ids: frozenset[str]
    ranked_ids: tuple[str, ...]
    latency_ms: float


@dataclass(frozen=True, slots=True)
class RetrievalEvaluation:
    query_count: int
    recall_at_k: float
    mrr: float
    ndcg_at_k: float
    p50_latency_ms: float
    p95_latency_ms: float


def evaluate_retrieval(
    observations: list[RetrievalObservation],
    *,
    k: int = 10,
) -> RetrievalEvaluation:
    if k < 1:
        raise ValueError("k must be positive")
    if not observations:
        return RetrievalEvaluation(0, 0.0, 0.0, 0.0, 0.0, 0.0)
    return RetrievalEvaluation(
        query_count=len(observations),
        recall_at_k=mean(_recall_at_k(item, k) for item in observations),
        mrr=mean(_reciprocal_rank(item) for item in observations),
        ndcg_at_k=mean(_ndcg_at_k(item, k) for item in observations),
        p50_latency_ms=_percentile([item.latency_ms for item in observations], 0.50),
        p95_latency_ms=_percentile([item.latency_ms for item in observations], 0.95),
    )


def _recall_at_k(observation: RetrievalObservation, k: int) -> float:
    if not observation.relevant_ids:
        return 1.0
    retrieved = set(observation.ranked_ids[:k])
    return len(retrieved & observation.relevant_ids) / len(observation.relevant_ids)


def _reciprocal_rank(observation: RetrievalObservation) -> float:
    for rank, item_id in enumerate(observation.ranked_ids, start=1):
        if item_id in observation.relevant_ids:
            return 1.0 / rank
    return 0.0


def _ndcg_at_k(observation: RetrievalObservation, k: int) -> float:
    gains = [
        1.0 / log2(rank + 1)
        for rank, item_id in enumerate(observation.ranked_ids[:k], start=1)
        if item_id in observation.relevant_ids
    ]
    ideal_count = min(k, len(observation.relevant_ids))
    ideal = sum(1.0 / log2(rank + 1) for rank in range(1, ideal_count + 1))
    return sum(gains) / ideal if ideal else 1.0


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction
