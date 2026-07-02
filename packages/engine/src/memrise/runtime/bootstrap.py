from memrise.consolidation.graph_projection import GraphProjectionService
from memrise.integrations.apache_age.repository import AgeGraphRepository
from memrise.integrations.postgres.repositories import PostgresMemoryStore
from memrise.integrations.postgres.session import make_session_factory
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
    graph_repository = AgeGraphRepository(
        session_factory,
        id_generator=id_generator,
        query_timeout_seconds=settings.memrise_graph_query_timeout_seconds,
    )
    completion = QwenCompletionProvider(settings)
    embeddings = QwenEmbeddingProvider(settings)
    return Memrise(
        store=store,
        jobs=store,
        graph_repository=graph_repository,
        graph_projection=GraphProjectionService(
            graph_repository=graph_repository,
            min_confidence=settings.memrise_graph_min_confidence,
        ),
        completion_provider=completion,
        embedding_provider=embeddings,
        token_counter=ApproximateTokenCounter(),
        feedback_policy=DefaultFeedbackPolicy(),
    )
