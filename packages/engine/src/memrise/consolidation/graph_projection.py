from memrise.core.models import CanonicalMemory
from memrise.graph.projection_builder import build_graph_projection
from memrise.ports.graph_repository import GraphRepository
from memrise.ports.providers import ExtractedGraphRelation


class GraphProjectionService:
    def __init__(
        self,
        *,
        graph_repository: GraphRepository,
        min_confidence: float = 0.5,
    ) -> None:
        self._graph_repository = graph_repository
        self._min_confidence = min_confidence

    async def project_memory(
        self,
        *,
        memory: CanonicalMemory,
        relations: list[ExtractedGraphRelation],
    ):
        projection = build_graph_projection(
            memory=memory,
            relations=relations,
            min_confidence=self._min_confidence,
        )
        if projection is None:
            return None
        if not await self._graph_repository.is_available():
            msg = "apache age is unavailable for graph projection"
            raise RuntimeError(msg)
        return await self._graph_repository.project(projection)
