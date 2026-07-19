#!/usr/bin/env python3
"""Benchmark filtered pgvector profiles against exact nearest-neighbor ground truth."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import asdict, dataclass
from statistics import mean
from time import perf_counter

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from memrise.integrations.postgres.schema.models import MemoryRow, MemoryVersionRow
from memrise.integrations.postgres.session import make_session_factory


@dataclass(frozen=True, slots=True)
class Profile:
    name: str
    iterative_scan: str
    ef_search: int


@dataclass(frozen=True, slots=True)
class Sample:
    version_id: str
    namespace_id: str
    agent_id: str
    user_id: str | None
    project_id: str | None
    embedding: list[float]
    embedding_model: str | None


PROFILES = (
    Profile("hnsw-off-40", "off", 40),
    Profile("hnsw-strict-100", "strict_order", 100),
    Profile("hnsw-relaxed-100", "relaxed_order", 100),
    Profile("hnsw-relaxed-200", "relaxed_order", 200),
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=50)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--min-recall", type=float, default=0.95)
    parser.add_argument("--p95-target-ms", type=float, default=50.0)
    return parser


async def _samples(
    factory: async_sessionmaker[AsyncSession],
    limit: int,
) -> list[Sample]:
    async with factory() as session:
        rows = (
            await session.execute(
                select(
                    MemoryVersionRow.id,
                    MemoryRow.namespace_id,
                    MemoryRow.agent_id,
                    MemoryRow.user_id,
                    MemoryRow.project_id,
                    MemoryVersionRow.embedding,
                    MemoryVersionRow.embedding_model,
                )
                .join(MemoryRow, MemoryVersionRow.memory_id == MemoryRow.id)
                .where(
                    MemoryVersionRow.status.in_(["active", "contested"]),
                    MemoryVersionRow.embedding.is_not(None),
                )
                .order_by(func.random())
                .limit(limit)
            )
        ).all()
    return [
        Sample(
            version_id=version_id,
            namespace_id=namespace_id,
            agent_id=agent_id,
            user_id=user_id,
            project_id=project_id,
            embedding=list(embedding),
            embedding_model=embedding_model,
        )
        for (
            version_id,
            namespace_id,
            agent_id,
            user_id,
            project_id,
            embedding,
            embedding_model,
        ) in rows
    ]


def _query(sample: Sample, *, k: int):
    distance = MemoryVersionRow.embedding.cosine_distance(sample.embedding)
    return (
        select(MemoryVersionRow.id)
        .join(MemoryRow, MemoryVersionRow.memory_id == MemoryRow.id)
        .where(
            MemoryRow.namespace_id == sample.namespace_id,
            MemoryRow.agent_id == sample.agent_id,
            or_(MemoryRow.user_id.is_(None), MemoryRow.user_id == sample.user_id),
            or_(MemoryRow.project_id.is_(None), MemoryRow.project_id == sample.project_id),
            MemoryVersionRow.status.in_(["active", "contested"]),
            MemoryVersionRow.embedding.is_not(None),
            or_(
                MemoryVersionRow.embedding_model.is_(None),
                MemoryVersionRow.embedding_model == sample.embedding_model,
            ),
        )
        .order_by(distance)
        .limit(k)
    )


async def _run_query(
    factory: async_sessionmaker[AsyncSession],
    sample: Sample,
    *,
    k: int,
    profile: Profile | None,
) -> tuple[list[str], float]:
    async with factory() as session, session.begin():
        if profile is None:
            await session.execute(text("SET LOCAL enable_indexscan = off"))
            await session.execute(text("SET LOCAL enable_bitmapscan = off"))
        else:
            await session.execute(text("SET LOCAL enable_indexscan = on"))
            await session.execute(
                text(f"SET LOCAL hnsw.iterative_scan = '{profile.iterative_scan}'")
            )
            await session.execute(text(f"SET LOCAL hnsw.ef_search = {profile.ef_search:d}"))
        started = perf_counter()
        ids = (await session.execute(_query(sample, k=k))).scalars().all()
        latency_ms = (perf_counter() - started) * 1_000
    return list(ids), latency_ms


async def _explain(
    factory: async_sessionmaker[AsyncSession],
    sample: Sample,
    *,
    k: int,
    profile: Profile,
) -> object:
    vector = "[" + ",".join(str(value) for value in sample.embedding) + "]"
    statement = text(
        "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) "
        "SELECT mv.id FROM memory_versions mv "
        "JOIN memories m ON mv.memory_id = m.id "
        "WHERE m.namespace_id = :namespace_id AND m.agent_id = :agent_id "
        "AND (m.user_id IS NULL OR m.user_id IS NOT DISTINCT FROM :user_id) "
        "AND (m.project_id IS NULL OR m.project_id IS NOT DISTINCT FROM :project_id) "
        "AND mv.status IN ('active', 'contested') AND mv.embedding IS NOT NULL "
        "AND (mv.embedding_model IS NULL OR mv.embedding_model IS NOT DISTINCT FROM :model) "
        "ORDER BY mv.embedding <=> CAST(:embedding AS vector) LIMIT :limit"
    )
    async with factory() as session, session.begin():
        await session.execute(text(f"SET LOCAL hnsw.iterative_scan = '{profile.iterative_scan}'"))
        await session.execute(text(f"SET LOCAL hnsw.ef_search = {profile.ef_search:d}"))
        plan = await session.scalar(
            statement,
            {
                "namespace_id": sample.namespace_id,
                "agent_id": sample.agent_id,
                "user_id": sample.user_id,
                "project_id": sample.project_id,
                "model": sample.embedding_model,
                "embedding": vector,
                "limit": k,
            },
        )
    return _summarize_plan(plan)


def _summarize_plan(plan: object) -> object:
    if not isinstance(plan, list) or not plan or not isinstance(plan[0], dict):
        return plan
    root = plan[0]
    nodes: list[dict[str, object]] = []

    def visit(node: object) -> None:
        if not isinstance(node, dict):
            return
        summary = {
            key: node[key]
            for key in (
                "Node Type",
                "Index Name",
                "Actual Rows",
                "Actual Total Time",
                "Rows Removed by Filter",
                "Shared Hit Blocks",
                "Shared Read Blocks",
            )
            if key in node
        }
        nodes.append(summary)
        for child in node.get("Plans", []):
            visit(child)

    visit(root.get("Plan"))
    return {
        "planning_time_ms": root.get("Planning Time"),
        "execution_time_ms": root.get("Execution Time"),
        "nodes": nodes,
        "uses_hnsw_index": any(
            node.get("Index Name") == "ix_memory_versions_embedding_hnsw" for node in nodes
        ),
    }


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


async def _main() -> int:
    args = _parser().parse_args()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")
    factory = make_session_factory(database_url)
    samples = await _samples(factory, args.samples)
    if not samples:
        raise SystemExit("no live embeddings are available to benchmark")
    exact = {}
    exact_latencies = []
    for sample in samples:
        ids, latency = await _run_query(factory, sample, k=args.k, profile=None)
        exact[sample.version_id] = ids
        exact_latencies.append(latency)

    reports = []
    for profile in PROFILES:
        recalls = []
        latencies = []
        for sample in samples:
            ids, latency = await _run_query(factory, sample, k=args.k, profile=profile)
            expected = set(exact[sample.version_id])
            recalls.append(len(expected & set(ids)) / len(expected) if expected else 1.0)
            latencies.append(latency)
        reports.append(
            {
                **asdict(profile),
                "mean_recall_at_k": mean(recalls),
                "p50_latency_ms": _percentile(latencies, 0.50),
                "p95_latency_ms": _percentile(latencies, 0.95),
            }
        )

    passing = [
        report
        for report in reports
        if report["mean_recall_at_k"] >= args.min_recall
        and report["p95_latency_ms"] <= args.p95_target_ms
    ]
    async with factory() as session:
        live_vectors = int(
            await session.scalar(
                select(func.count())
                .select_from(MemoryVersionRow)
                .where(
                    MemoryVersionRow.status.in_(["active", "contested"]),
                    MemoryVersionRow.embedding.is_not(None),
                )
            )
            or 0
        )
        index_bytes = int(
            await session.scalar(
                text("SELECT pg_relation_size('ix_memory_versions_embedding_hnsw')")
            )
            or 0
        )
    trial_pgvectorscale = live_vectors >= 1_000_000 and not passing
    report = {
        "sample_count": len(samples),
        "k": args.k,
        "live_vector_count": live_vectors,
        "hnsw_index_bytes": index_bytes,
        "exact_p95_latency_ms": _percentile(exact_latencies, 0.95),
        "profiles": reports,
        "explain_analyze": await _explain(
            factory,
            samples[0],
            k=args.k,
            profile=PROFILES[2],
        ),
        "decision": {
            "action": "trial_pgvectorscale" if trial_pgvectorscale else "keep_pgvector_hnsw",
            "reason": (
                "At least one HNSW profile meets the target, or the corpus is below "
                "the one-million-vector scale gate."
                if not trial_pgvectorscale
                else "The corpus is at least one million vectors and no HNSW profile "
                "meets both recall and p95 latency targets."
            ),
        },
    }
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
