import pytest
from tests.mocks.graph_store import GraphClaimStoreStub

from memrise.graph.entities import EntityMention, EntityResolver, query_search_terms
from memrise.graph.identity import stable_entity_id


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
