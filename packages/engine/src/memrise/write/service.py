from dataclasses import dataclass
from datetime import datetime

from memrise.core.enums import JobType
from memrise.core.models import Episode
from memrise.ports.providers import CompletionProvider, EmbeddingProvider
from memrise.ports.repositories import JobQueue, MemoryStore
from memrise.runtime.scope import scope_from_namespace_agent
from memrise.write.importance import ImportanceGate


@dataclass(frozen=True, slots=True)
class ExtractionOutcome:
    created_memory_version_ids: list[str]
    graph_projection_job_ids: list[str]


class WriteService:
    def __init__(
        self,
        *,
        store: MemoryStore,
        jobs: JobQueue,
        completion_provider: CompletionProvider,
        embedding_provider: EmbeddingProvider,
        importance_gate: ImportanceGate,
    ) -> None:
        self._store = store
        self._jobs = jobs
        self._completion_provider = completion_provider
        self._embedding_provider = embedding_provider
        self._importance_gate = importance_gate

    async def capture_episode(self, episode: Episode) -> str | None:
        await self._store.save_episode(episode)
        if not self._importance_gate.should_extract(episode.content):
            return None
        return await self._jobs.enqueue(
            job_type=JobType.EXTRACT_EPISODE,
            payload={"episode_id": episode.id},
            dedupe_key=f"extract:{episode.id}",
        )

    async def extract_episode(self, episode_id: str, now: datetime) -> ExtractionOutcome:
        episode = await self._store.get_episode(episode_id)
        if episode is None:
            return ExtractionOutcome(created_memory_version_ids=[], graph_projection_job_ids=[])
        scope = scope_from_namespace_agent(
            namespace_id=episode.namespace_id,
            agent_id=episode.agent_id,
            user_id=episode.user_id,
            project_id=episode.project_id,
        )
        extraction = await self._completion_provider.extract_memories(
            text=episode.content,
            context={
                "namespace_id": episode.namespace_id,
                "agent_id": episode.agent_id,
                "session_id": episode.session_id,
                "project_id": episode.project_id,
            },
        )
        created: list[str] = []
        graph_jobs: list[str] = []
        for candidate in extraction.candidates:
            embedding = await self._embedding_provider.embed(candidate.content)
            memory = await self._store.apply_candidate(
                scope=scope,
                candidate=candidate,
                source_episode_ids=[episode.id],
                embedding=embedding,
            )
            if memory is None:
                continue
            job_id = await self._store.schedule_graph_projection(
                memory=memory,
                relations=candidate.graph_relations,
            )
            if job_id is not None:
                graph_jobs.append(job_id)
            created.append(memory.version.id)
        del now
        return ExtractionOutcome(
            created_memory_version_ids=created,
            graph_projection_job_ids=graph_jobs,
        )
