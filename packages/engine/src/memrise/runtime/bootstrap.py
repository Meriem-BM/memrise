from memrise.graph.projection import GraphProjectionService, GraphRebuildService
from memrise.integrations.apache_age.repository import AgeGraphRepository
from memrise.integrations.postgres import (
    PostgresJobQueue,
    PostgresMemoryStore,
    make_session_factory,
)
from memrise.integrations.postgres.store.graph_claims import PostgresGraphClaimStore
from memrise.integrations.postgres.store.schema_registry import PostgresGraphSchemaRegistry
from memrise.integrations.qwen.providers import QwenCompletionProvider, QwenEmbeddingProvider
from memrise.learning.policy import DefaultFeedbackPolicy
from memrise.runtime.ids import UuidGenerator
from memrise.runtime.memory import Memrise
from memrise.runtime.settings import MemorySettings
from memrise.runtime.token_counter import ApproximateTokenCounter


def build_postgres_memory(settings: MemorySettings) -> Memrise:
    if settings.database_url is None:
        msg = "DATABASE_URL is required for PostgreSQL runtime"
        raise ValueError(msg)

    session_factory = make_session_factory(settings.database_url)
    id_generator = UuidGenerator()
    store = PostgresMemoryStore(session_factory, id_generator=id_generator)
    jobs = PostgresJobQueue(session_factory, id_generator=id_generator)
    graph_repository = AgeGraphRepository(
        session_factory,
        id_generator=id_generator,
        query_timeout_seconds=settings.memrise_graph_query_timeout_seconds,
    )
    graph_claim_store = PostgresGraphClaimStore(session_factory)
    schema_registry = PostgresGraphSchemaRegistry(session_factory, id_generator=id_generator)
    graph_projection = GraphProjectionService(
        graph_repository=graph_repository,
        graph_claim_store=graph_claim_store,
        schema_registry=schema_registry,
        min_confidence=settings.memrise_graph_min_confidence,
    )
    graph_rebuild = GraphRebuildService(
        claim_store=graph_claim_store,
        memory_store=store,
        graph_projection=graph_projection,
    )

    return Memrise(
        store=store,
        jobs=jobs,
        graph_repository=graph_repository,
        graph_claim_store=graph_claim_store,
        graph_projection=graph_projection,
        graph_rebuild=graph_rebuild,
        schema_registry=schema_registry,
        completion_provider=QwenCompletionProvider(settings),
        embedding_provider=QwenEmbeddingProvider(settings),
        token_counter=ApproximateTokenCounter(),
        feedback_policy=DefaultFeedbackPolicy(),
        usefulness_half_life_days=settings.memrise_usefulness_half_life_days,
    )
