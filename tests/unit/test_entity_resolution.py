from datetime import UTC, datetime

import pytest

from memrise.graph.entities import EntityMention, EntityResolver, query_search_terms
from memrise.graph.identity import stable_entity_id
from tests.mocks.graph_store import GraphClaimStoreStub


@pytest.mark.asyncio
async def test_entity_resolver_creates_new_entity_when_no_match() -> None:
    store = GraphClaimStoreStub()
    resolver = EntityResolver(claim_store=store)

    result = await resolver.resolve(
        mention=EntityMention(name="Atlas"),
        namespace_id="ns-1",
        core_type="Project",
    )

    assert result.status == "new_entity"
    assert result.entity_id is not None
    assert result.canonical_name == "Atlas"
    assert result.core_type == "Project"


@pytest.mark.asyncio
async def test_entity_resolver_finds_existing_entity_by_identity() -> None:
    store = GraphClaimStoreStub()
    resolver = EntityResolver(claim_store=store)
    first = await resolver.resolve(
        mention=EntityMention(name="Atlas"),
        namespace_id="ns-1",
        core_type="Project",
    )
    assert first.entity_id is not None
    await store.upsert_entity(
        entity_id=first.entity_id,
        namespace_id="ns-1",
        core_type="Project",
        canonical_name="Atlas",
        normalized_name="atlas",
        aliases=("Atlas",),
    )

    second = await resolver.resolve(
        mention=EntityMention(name="Atlas"),
        namespace_id="ns-1",
        core_type="Project",
    )

    assert second.status == "resolved"
    assert second.entity_id == first.entity_id


def test_query_search_terms_prefers_phrases_before_single_tokens() -> None:
    terms = query_search_terms("Who works on Acme Billing?")

    assert terms[0] == "Who works on Acme Billing"
    assert "Acme Billing" in terms
    assert terms.index("Acme Billing") < terms.index("Acme")


@pytest.mark.asyncio
async def test_resolve_query_terms_matches_multi_word_entity_name() -> None:
    store = GraphClaimStoreStub()
    entity_id = stable_entity_id(namespace_id="ns-1", core_type="Organization", name="Acme Billing")
    await store.upsert_entity(
        entity_id=entity_id,
        namespace_id="ns-1",
        core_type="Organization",
        canonical_name="Acme Billing",
        normalized_name="acme billing",
        aliases=("Acme Billing",),
    )
    resolver = EntityResolver(claim_store=store)

    resolved = await resolver.resolve_query_terms(
        namespace_id="ns-1",
        query="Who works on Acme Billing?",
    )

    assert len(resolved) == 1
    assert resolved[0].id == entity_id


@pytest.mark.asyncio
async def test_resolve_query_terms_matches_alias_entry() -> None:
    store = GraphClaimStoreStub()
    entity_id = stable_entity_id(namespace_id="ns-1", core_type="Project", name="Atlas")
    await store.upsert_entity(
        entity_id=entity_id,
        namespace_id="ns-1",
        core_type="Project",
        canonical_name="Atlas Platform",
        normalized_name="atlas platform",
        aliases=("Atlas",),
    )
    resolver = EntityResolver(claim_store=store)

    resolved = await resolver.resolve_query_terms(
        namespace_id="ns-1",
        query="What depends on Atlas?",
    )

    assert len(resolved) == 1
    assert resolved[0].id == entity_id


async def test_multiple_alias_matches_with_one_exact_name_resolve() -> None:
    store = GraphClaimStoreStub()
    await store.upsert_entity(
        entity_id="gent-postgres",
        namespace_id="ns",
        core_type="Technology",
        canonical_name="Postgres",
        normalized_name="postgres",
        aliases=("Postgres", "PostgreSQL Database"),
    )
    await store.upsert_entity(
        entity_id="gent-postgrest",
        namespace_id="ns",
        core_type="Technology",
        canonical_name="PostgREST",
        normalized_name="postgrest",
        aliases=("PostgREST", "postgres rest api"),
    )
    resolver = EntityResolver(claim_store=store)

    result = await resolver.resolve(
        mention=EntityMention(name="postgres"),
        namespace_id="ns",
        core_type="Technology",
    )

    assert result.status == "resolved"
    assert result.entity_id == "gent-postgres"


async def test_merge_entities_moves_claims_and_unions_aliases() -> None:
    store = GraphClaimStoreStub()
    keep = await store.upsert_entity(
        entity_id="gent-keep",
        namespace_id="ns",
        core_type="Technology",
        canonical_name="PostgreSQL",
        normalized_name="postgresql",
        aliases=("PostgreSQL",),
    )
    drop = await store.upsert_entity(
        entity_id="gent-drop",
        namespace_id="ns",
        core_type="Technology",
        canonical_name="Postgres",
        normalized_name="postgres",
        aliases=("Postgres", "pg"),
    )
    claim = await store.insert_claim_if_absent(
        claim_id="gclm-1",
        namespace_id="ns",
        subject_entity_id="gent-subject",
        predicate="USES",
        object_entity_id=drop.id,
        supporting_memory_version_id="memv_1",
        evidence_text="Atlas uses Postgres.",
        confidence=0.9,
        valid_from=datetime(2026, 7, 3, tzinfo=UTC),
        schema_version="core@1.0",
        extractor_version=None,
        extracted_at=datetime(2026, 7, 3, tzinfo=UTC),
    )

    moved = await store.merge_entities(
        namespace_id="ns",
        source_entity_id=drop.id,
        target_entity_id=keep.id,
    )

    assert moved == 1
    assert store.claims[claim.id].object_entity_id == keep.id
    assert drop.id not in store.entities
    merged = store.entities[keep.id]
    assert {"PostgreSQL", "Postgres", "pg"} <= set(merged.aliases)
