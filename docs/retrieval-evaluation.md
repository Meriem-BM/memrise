# Retrieval evaluation

Memrise changes retrieval infrastructure only against measured quality and latency.
The source of truth remains PostgreSQL; external search systems, if ever introduced,
must be rebuildable projections.

## Quality gate

`tests/eval/retrieval_cases.json` contains 20 memory scenarios and 120 labeled
queries spanning identifiers, paraphrases, constraints, operational facts, and
policy questions. The evaluation reports:

- Recall@10
- Mean reciprocal rank
- nDCG@10
- p50 and p95 engine latency

Run it with:

```bash
uv run pytest tests/eval/test_retrieval_quality.py
```

Production ranking changes should add or update cases that represent the failure
being fixed. Do not tune against the test set alone; split a larger real trace set
into training and validation partitions before changing channel weights.

## PostgreSQL benchmark

The database benchmark samples live embeddings, computes exact pgvector neighbors
with ANN indexes disabled, then compares four filtered HNSW profiles:

```bash
make benchmark-retrieval
```

Optional controls:

```bash
uv run python scripts/benchmark_retrieval.py \
  --samples 100 \
  --k 10 \
  --min-recall 0.95 \
  --p95-target-ms 50
```

The JSON report includes Recall@k, p50/p95 latency, index size, an
`EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` plan, and an adoption decision.

## pgvectorscale gate

Keep pgvector HNSW while at least one tested profile meets both the recall and p95
targets, or while the corpus has fewer than one million live vectors. Trial
pgvectorscale StreamingDiskANN only when:

1. the corpus contains at least one million live vectors;
2. no pgvector HNSW profile meets both targets;
3. the trial uses the same sampled queries and exact-neighbor ground truth;
4. PostgreSQL remains authoritative and downgrade/reindex behavior is proven.

This threshold is intentionally empirical. Installing another index extension
without a failing benchmark adds operational risk without demonstrating a product
benefit.

## Reranking

Set `MEMRISE_RERANKER_ENABLED=true` to apply the bounded Qwen reranker after
candidate fusion. `MEMRISE_RERANKER_CANDIDATE_LIMIT` defaults to 30 and
`MEMRISE_RERANKER_WEIGHT` defaults to 0.35. The reranker never generates
candidates and cannot bypass scope, lifecycle, task applicability, or critical
memory handling.

Because reranking adds a provider call, leave it disabled until an evaluation shows
enough precision improvement to justify its latency and cost.
