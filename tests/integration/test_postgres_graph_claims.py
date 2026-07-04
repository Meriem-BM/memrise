from uuid import uuid4

import pytest

from memrise.graph.types import normalize_entity_name
from memrise.integrations.postgres import make_session_factory
from memrise.integrations.postgres.store.graph_claims import PostgresGraphClaimStore
from tests.integration.db import database_url

pytestmark = pytest.mark.asyncio


async def test_find_entities_by_term_matches_aliases() -> None:
    store = PostgresGraphClaimStore(make_session_factory(database_url()))
    namespace_id = f"it-graph-alias-{uuid4().hex}"
    entity = await store.upsert_entity(
        entity_id=f"gent-{uuid4().hex}",
        namespace_id=namespace_id,
        core_type="person",
        canonical_name="Lina",
        normalized_name=normalize_entity_name("Lina"),
        aliases=("Hello, my name is Lina",),
        project_id="atlas",
    )

    matches = await store.find_entities_by_term(
        namespace_id=namespace_id,
        term="Hello, my name is Lina",
        project_id="atlas",
    )

    assert [match.id for match in matches] == [entity.id]
