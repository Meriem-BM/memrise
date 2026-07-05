from datetime import UTC, datetime
from uuid import uuid4

import pytest

from memrise.core.enums import Criticality, MemoryStatus, MemoryType
from memrise.core.models import Scope
from memrise.integrations.postgres import PostgresMemoryStore, make_session_factory
from memrise.ports.providers import EmbeddingVector, ExtractedMemoryCandidate
from memrise.runtime.ids import UuidGenerator
from tests.integration.db import database_url

pytestmark = pytest.mark.asyncio


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
    # Near-identical embeddings; different subject/key so reconciliation never merged them.
    vector = EmbeddingVector(values=[0.2] * 1024, model="mock-embedding", dimensions=1024)

    survivor = await store.apply_candidate(
        scope=scope,
        candidate=_candidate("lockfile", "rule", "Never manually edit the generated lockfile."),
        source_episode_ids=[],
        embedding=vector,
    )
    duplicate = await store.apply_candidate(
        scope=scope,
        candidate=_candidate("pnpm_lockfile", "edit", "Never manually edit the pnpm lockfile."),
        source_episode_ids=[],
        embedding=vector,
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
