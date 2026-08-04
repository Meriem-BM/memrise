from uuid import uuid4

import pytest

from memrise.core.enums import Criticality, MemoryType
from memrise.core.models import Scope
from memrise.integrations.postgres import PostgresMemoryStore, make_session_factory
from memrise.ports.providers import EmbeddingVector, ExtractedMemoryCandidate
from memrise.runtime.ids import UuidGenerator
from tests.integration.db import database_url

pytestmark = pytest.mark.asyncio


def _candidate(subject: str, key: str, content: str) -> ExtractedMemoryCandidate:
    return ExtractedMemoryCandidate(
        type=MemoryType.FACT,
        subject=subject,
        key=key,
        content=content,
        confidence=0.9,
        importance=0.7,
        criticality=Criticality.NORMAL,
        evidence_quote=content,
        search_text=f"{subject} {key}",
    )


async def test_postgres_store_uses_bm25_lexical_ranking() -> None:
    store = PostgresMemoryStore(
        make_session_factory(database_url()),
        id_generator=UuidGenerator(),
    )
    scope = Scope(
        namespace_id=f"it-bm25-{uuid4().hex}",
        agent_id="coding-agent",
        user_id="user-1",
        project_id="atlas",
    )
    first = await store.apply_candidate(
        scope=scope,
        candidate=_candidate(
            "Atlas",
            "package_manager",
            "Atlas dependency installs use the pnpm package manager.",
        ),
        source_episode_ids=[],
        embedding=EmbeddingVector(values=[0.2] * 1024, model="test", dimensions=1024),
    )
    await store.apply_candidate(
        scope=scope,
        candidate=_candidate(
            "Atlas",
            "deploy_day",
            "Atlas production deployments happen on Fridays.",
        ),
        source_episode_ids=[],
        embedding=EmbeddingVector(
            values=[0.2] * 512 + [-0.2] * 512,
            model="test",
            dimensions=1024,
        ),
    )
    assert first.memory is not None

    hits = await store.search_lexical(
        scope=scope,
        query="dependency package manager pnpm",
        limit=10,
    )

    assert hits
    assert hits[0][0].version.id == first.memory.version.id
    assert hits[0][1] > 0


async def test_filtered_hnsw_profile_returns_scoped_semantic_hit() -> None:
    store = PostgresMemoryStore(
        make_session_factory(database_url()),
        id_generator=UuidGenerator(),
        hnsw_iterative_scan="strict_order",
        hnsw_ef_search=120,
    )
    scope = Scope(
        namespace_id=f"it-hnsw-{uuid4().hex}",
        agent_id="coding-agent",
        user_id="user-1",
        project_id="atlas",
    )
    vector = EmbeddingVector(values=[0.3] * 1024, model="test", dimensions=1024)
    outcome = await store.apply_candidate(
        scope=scope,
        candidate=_candidate("Atlas", "runtime", "Atlas runs on Python."),
        source_episode_ids=[],
        embedding=vector,
    )
    assert outcome.memory is not None

    hits = await store.search_semantic(scope=scope, embedding=vector, limit=5)

    assert hits
    assert hits[0][0].version.id == outcome.memory.version.id
