import pytest

from memrise.read.evaluation import RetrievalObservation, evaluate_retrieval


def test_retrieval_metrics_include_quality_and_latency() -> None:
    evaluation = evaluate_retrieval(
        [
            RetrievalObservation(
                query_id="q1",
                relevant_ids=frozenset({"a"}),
                ranked_ids=("a", "b"),
                latency_ms=10,
            ),
            RetrievalObservation(
                query_id="q2",
                relevant_ids=frozenset({"c"}),
                ranked_ids=("x", "c"),
                latency_ms=30,
            ),
        ],
        k=2,
    )

    assert evaluation.recall_at_k == 1.0
    assert evaluation.mrr == 0.75
    assert evaluation.ndcg_at_k == pytest.approx((1 + 1 / 1.584962500721156) / 2)
    assert evaluation.p50_latency_ms == 20
    assert evaluation.p95_latency_ms == 29
