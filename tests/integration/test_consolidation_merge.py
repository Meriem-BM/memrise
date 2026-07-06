from datetime import UTC, datetime
from uuid import uuid4

import pytest

from memrise.core.enums import Criticality, JobType, MemoryStatus, MemoryType
from memrise.core.models import Scope
from memrise.integrations.postgres import (
    PostgresJobQueue,
    PostgresMemoryStore,
    make_session_factory,
)
from memrise.ports.providers import EmbeddingVector, ExtractedMemoryCandidate
from memrise.runtime.ids import UuidGenerator
from tests.integration.db import database_url

pytestmark = pytest.mark.asyncio


async def test_dedupe_memories_job_type_is_allowed_by_constraint() -> None:
    # Guards the ck_jobs_type check constraint against drifting from the JobType enum.
    queue = PostgresJobQueue(make_session_factory(database_url()), id_generator=UuidGenerator())
    job_id = await queue.enqueue(
        job_type=JobType.DEDUPE_MEMORIES,
        payload={},
        dedupe_key=f"dedupe-test-{uuid4().hex}",
    )
    assert job_id


def _candidate(subject: str, key: str, content: str) -> ExtractedMemoryCandidate:
    return ExtractedMemoryCandidate(
        type=MemoryType.CONSTRAINT,
        subject=subject,
        key=key,
        content=content,
        structured_value={},
        confidence=0.9,
        importance=0.8,
        criticality=Criticality.NORMAL,
        evidence_quote=content,
    )


async def test_supersede_merges_duplicates_and_preserves_history() -> None:
    store = PostgresMemoryStore(make_session_factory(database_url()), id_generator=UuidGenerator())
    scope = Scope(
        namespace_id=f"it-merge-{uuid4().hex}",
        agent_id="coding-agent",
        user_id="user-1",
        project_id="atlas",
    )
    # Dissimilar embeddings so write-time prevention does not merge them here: this
    # test exercises the SQL supersession directly with explicit version ids.
    vector_a = EmbeddingVector(values=[0.2] * 1024, model="mock-embedding", dimensions=1024)
    vector_b = EmbeddingVector(
        values=[0.2] * 512 + [-0.2] * 512, model="mock-embedding", dimensions=1024
    )

    survivor = await store.apply_candidate(
        scope=scope,
        candidate=_candidate("lockfile", "rule", "Never manually edit the generated lockfile."),
        source_episode_ids=[],
        embedding=vector_a,
    )
    duplicate = await store.apply_candidate(
        scope=scope,
        candidate=_candidate("pnpm_lockfile", "edit", "Never manually edit the pnpm lockfile."),
        source_episode_ids=[],
        embedding=vector_b,
    )
    assert survivor.memory is not None
    assert duplicate.memory is not None
    survivor_version_id = survivor.memory.version.id
    duplicate_version_id = duplicate.memory.version.id

    superseded = await store.supersede_memories_as_duplicates(
        survivor_version_id=survivor_version_id,
        duplicate_version_ids=[duplicate_version_id],
        now=datetime.now(UTC),
    )
    assert superseded == 1

    # Only the survivor is live now.
    active = await store.list_active_memories(scope=scope)
    active_ids = {memory.version.id for memory in active}
    assert survivor_version_id in active_ids
    assert duplicate_version_id not in active_ids

    # The duplicate is not physically deleted: it is retrievable as superseded history.
    superseded_memory = await store.get_memory_version_by_id(duplicate_version_id)
    assert superseded_memory is not None
    assert superseded_memory.version.status == MemoryStatus.SUPERSEDED
    assert superseded_memory.version.superseded_by_version_id == survivor_version_id


async def test_list_active_scopes_returns_distinct_live_scopes() -> None:
    store = PostgresMemoryStore(make_session_factory(database_url()), id_generator=UuidGenerator())
    ns = f"it-scopes-{uuid4().hex}"
    vector = EmbeddingVector(values=[0.4] * 1024, model="mock-embedding", dimensions=1024)
    orthogonal = EmbeddingVector(
        values=[0.4] * 512 + [-0.4] * 512, model="mock-embedding", dimensions=1024
    )
    scope_a = Scope(namespace_id=ns, agent_id="coding-agent", user_id="user-1", project_id="atlas")
    scope_b = Scope(namespace_id=ns, agent_id="coding-agent", user_id="user-1", project_id="orion")

    await store.apply_candidate(
        scope=scope_a,
        candidate=_candidate("atlas", "pm", "Atlas uses pnpm."),
        source_episode_ids=[],
        embedding=vector,
    )
    await store.apply_candidate(
        scope=scope_b,
        candidate=_candidate("orion", "pm", "Orion uses bun."),
        source_episode_ids=[],
        embedding=orthogonal,
    )

    scopes = await store.list_active_scopes()
    mine = {(s.namespace_id, s.project_id) for s in scopes if s.namespace_id == ns}
    assert mine == {(ns, "atlas"), (ns, "orion")}


async def test_write_time_prevention_reinforces_instead_of_duplicating() -> None:
    store = PostgresMemoryStore(make_session_factory(database_url()), id_generator=UuidGenerator())
    scope = Scope(
        namespace_id=f"it-prevent-{uuid4().hex}",
        agent_id="coding-agent",
        user_id="user-1",
        project_id="atlas",
    )
    vector = EmbeddingVector(values=[0.3] * 1024, model="mock-embedding", dimensions=1024)

    first = await store.apply_candidate(
        scope=scope,
        candidate=_candidate("lockfile", "rule", "Never manually edit the generated lockfile."),
        source_episode_ids=[],
        embedding=vector,
    )
    # Same meaning, different subject/key: reconciliation alone would add a 2nd memory.
    second = await store.apply_candidate(
        scope=scope,
        candidate=_candidate("pnpm_lockfile", "edit", "Never manually edit the pnpm lockfile."),
        source_episode_ids=[],
        embedding=vector,
    )

    assert first.memory is not None
    # No duplicate is created; the write reinforces the existing memory.
    active = await store.list_active_memories(scope=scope)
    assert len(active) == 1
    assert active[0].identity.id == first.memory.identity.id
    assert second.memory is not None
    assert second.memory.identity.id == first.memory.identity.id
