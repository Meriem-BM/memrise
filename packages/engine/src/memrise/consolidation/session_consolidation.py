from datetime import datetime

from memrise.ports.repositories import MemoryStore
from memrise.schemas.requests import ConsolidateRequest
from memrise.write.service import WriteService


class SessionConsolidationService:
    """Interim consolidation: ensure every session episode has been extracted.

    LLM-backed cross-episode consolidation (`consolidation_v1`) is not wired yet.
    """

    def __init__(self, *, store: MemoryStore, write: WriteService) -> None:
        self._store = store
        self._write = write

    async def consolidate_session(self, request: ConsolidateRequest, now: datetime) -> None:
        episodes = await self._store.list_session_episodes(
            namespace_id=request.namespace_id,
            agent_id=request.agent_id,
            session_id=request.session_id,
        )
        for episode in episodes:
            await self._write.extract_episode(episode.id, now)
