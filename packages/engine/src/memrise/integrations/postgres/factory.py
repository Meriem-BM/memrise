from memrise.integrations.in_memory.providers import (
    DeterministicCompletionProvider,
    DeterministicEmbeddingProvider,
)
from memrise.integrations.postgres.repositories import PostgresMemoryStore
from memrise.integrations.postgres.session import make_session_factory
from memrise.integrations.qwen.providers import QwenCompletionProvider, QwenEmbeddingProvider
from memrise.runtime.memory import Memory
from memrise.runtime.settings import MemorySettings
from memrise.services.outcome_learning import DefaultFeedbackPolicy
from memrise.services.token_counter import ApproximateTokenCounter


def build_postgres_memory(settings: MemorySettings) -> Memory:
    if settings.database_url is None:
        msg = "DATABASE_URL is required for PostgreSQL runtime"
        raise ValueError(msg)
    store = PostgresMemoryStore(make_session_factory(settings.database_url))
    if settings.memrise_use_fake_model:
        completion = DeterministicCompletionProvider()
        embeddings = DeterministicEmbeddingProvider(settings.qwen_embedding_dimensions)
    else:
        completion = QwenCompletionProvider(settings)
        embeddings = QwenEmbeddingProvider(settings)
    return Memory(
        store=store,
        jobs=store,
        completion_provider=completion,
        embedding_provider=embeddings,
        token_counter=ApproximateTokenCounter(),
        feedback_policy=DefaultFeedbackPolicy(),
    )
