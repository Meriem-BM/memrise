from memrise.read.query_embedding_cache import QueryEmbeddingCache
from tests.mocks.providers import MockEmbeddingProvider


async def test_repeated_query_hits_cache() -> None:
    provider = MockEmbeddingProvider()
    cache = QueryEmbeddingCache(provider)

    await cache.embed_query("How do I install Atlas?")
    await cache.embed_query("how do I install atlas?")  # same after normalization
    await cache.embed_query("  How do I install Atlas?  ")

    # Only the first distinct normalized query touches the provider.
    assert provider.embed_calls == 1


async def test_distinct_queries_each_embed_once() -> None:
    provider = MockEmbeddingProvider()
    cache = QueryEmbeddingCache(provider)

    await cache.embed_query("install atlas")
    await cache.embed_query("deploy atlas")
    await cache.embed_query("install atlas")  # cached

    assert provider.embed_calls == 2


async def test_lru_eviction_is_bounded() -> None:
    provider = MockEmbeddingProvider()
    cache = QueryEmbeddingCache(provider, max_size=2)

    await cache.embed_query("a")
    await cache.embed_query("b")
    await cache.embed_query("c")  # evicts "a"
    await cache.embed_query("a")  # miss again -> re-embed

    assert provider.embed_calls == 4
