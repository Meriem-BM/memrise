from memrise.integrations.qwen.providers import _EMBED_BATCH_LIMIT
from tests.mocks.providers import MockEmbeddingProvider


async def test_embed_many_returns_one_vector_per_text() -> None:
    provider = MockEmbeddingProvider(vector=[0.5, 0.5])
    vectors = await provider.embed_many(["a", "b", "c"])
    assert len(vectors) == 3
    assert all(v.dimensions == 2 for v in vectors)
    assert provider.embedded_texts == ["a", "b", "c"]


async def test_embed_many_empty_is_noop() -> None:
    provider = MockEmbeddingProvider()
    assert await provider.embed_many([]) == []
    assert provider.embed_many_calls == 1


def test_batch_limit_is_reasonable() -> None:
    # Guards the DashScope per-request cap the Qwen adapter chunks on.
    assert 1 <= _EMBED_BATCH_LIMIT <= 25
