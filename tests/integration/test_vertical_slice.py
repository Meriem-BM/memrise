import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from memrise import Memrise
from memrise.core.enums import EpisodeKind, FeedbackOutcome, FeedbackSource
from tests.integration.db import database_url

DEMO_EPISODE = (
    "Atlas used npm before, but we now use pnpm. Never edit its generated lockfile manually."
)

pytestmark = pytest.mark.asyncio


async def test_pgvector_extension_and_indexes_exist() -> None:
    engine = create_async_engine(database_url())
    async with engine.connect() as connection:
        extension = await connection.scalar(
            text("select extname from pg_extension where extname = 'vector'")
        )
        assert extension == "vector"
        indexes = (
            (
                await connection.execute(
                    text(
                        "select indexname from pg_indexes "
                        "where tablename in ("
                        "'memories','memory_versions','jobs','memory_candidates'"
                        ") "
                        "and indexname in ("
                        "'ix_memory_versions_embedding_hnsw',"
                        "'ix_memory_versions_search_gin',"
                        "'ix_jobs_claim',"
                        "'ix_memory_candidates_episode',"
                        "'ix_memory_candidates_scope_status',"
                        "'uq_memories_logical_identity',"
                        "'uq_memory_versions_version_number'"
                        ")"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert {
            "ix_memory_versions_embedding_hnsw",
            "ix_memory_versions_search_gin",
            "ix_jobs_claim",
            "ix_memory_candidates_episode",
            "ix_memory_candidates_scope_status",
            "uq_memories_logical_identity",
            "uq_memory_versions_version_number",
        } <= set(indexes)
    await engine.dispose()


async def test_vertical_slice_end_to_end() -> None:
    memory = Memrise.from_env()
    capture = await memory.capture(
        namespace_id="it",
        agent_id="coding-agent",
        session_id="session-1",
        user_id="user-1",
        project_id="atlas",
        events=[
            {
                "kind": EpisodeKind.USER_MESSAGE,
                "content": DEMO_EPISODE,
                "metadata": {},
            }
        ],
    )
    assert capture.episode_ids
    assert capture.job_ids
    assert await memory.process_job_once("it-worker")
    engine = create_async_engine(database_url())
    async with engine.connect() as connection:
        promoted_candidates = await connection.scalar(
            text(
                "select count(*) from memory_candidates "
                "where namespace_id = 'it' and status = 'promoted'"
            )
        )
    await engine.dispose()
    assert promoted_candidates is not None
    assert promoted_candidates >= 1

    result = await memory.retrieve(
        namespace_id="it",
        agent_id="coding-agent",
        user_id="user-1",
        project_id="atlas",
        query="How should I install dependencies for Atlas?",
        task_type="dependency_install",
        token_budget=800,
        limit=10,
    )
    assert "pnpm" in result.context

    lockfile = await memory.retrieve(
        namespace_id="it",
        agent_id="coding-agent",
        user_id="user-1",
        project_id="atlas",
        query="Update the Atlas lockfile.",
        task_type="lockfile_update",
        token_budget=800,
        limit=10,
    )
    assert lockfile.critical
    assert "lockfile" in lockfile.context.lower()
    assert "edit" in lockfile.context.lower()

    returned = result.memories[0]
    feedback = await memory.feedback(
        result.retrieval_id,
        outcome=FeedbackOutcome.HELPFUL,
        source=FeedbackSource.DEVELOPER,
        memory_version_id=returned.memory_version_id,
    )
    assert feedback.usefulness_score is not None
    assert feedback.usefulness_score > returned.usefulness_score


async def test_two_workers_do_not_claim_same_job() -> None:
    memory = Memrise.from_env()
    capture = await memory.capture(
        namespace_id="it-claim",
        agent_id="coding-agent",
        session_id="session-claim",
        project_id="atlas",
        events=[{"kind": "user_message", "content": "Atlas uses pnpm.", "metadata": {}}],
    )
    assert capture.job_ids
    first = await memory.jobs.claim_next(worker_id="worker-a")
    second = await memory.jobs.claim_next(worker_id="worker-b")
    assert first is not None
    assert second is None or second.id != first.id
    await memory.jobs.complete(first.id)
