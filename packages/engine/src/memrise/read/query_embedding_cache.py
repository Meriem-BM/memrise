from collections import OrderedDict

from memrise.core.text import normalize_lookup
from memrise.ports.providers import EmbeddingProvider, EmbeddingVector

DEFAULT_QUERY_CACHE_SIZE = 256


class QueryEmbeddingCache:
    """Bounded LRU over normalized-query embeddings for the retrieval hot path.

    Retrieval embeds the query on every request; agents re-ask the same or
    near-identical questions, so caching the vector removes a provider round trip
    from the hot path. A query embedding is a pure function of the query text and
    the embedding model, both fixed within a process, so cached vectors never need
    explicit invalidation - the size bound is the only eviction.
    """

    def __init__(
        self,
        provider: EmbeddingProvider,
        *,
        max_size: int = DEFAULT_QUERY_CACHE_SIZE,
    ) -> None:
        self._provider = provider
        self._max_size = max_size
        self._cache: OrderedDict[str, EmbeddingVector] = OrderedDict()

    async def embed_query(self, query: str) -> EmbeddingVector:
        key = normalize_lookup(query)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return cached
        vector = await self._provider.embed(query)
        self._cache[key] = vector
        self._cache.move_to_end(key)
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)
        return vector
