from dataclasses import dataclass
from datetime import datetime

from memrise.core.enums import CandidateStageStatus, JobType
from memrise.core.models import (
    ApplyCandidateOutcome,
    CanonicalMemory,
    Episode,
    MemoryCandidateStage,
)
from memrise.graph.schema import InMemoryGraphSchemaRegistry, route_schema_packs
from memrise.integrations.qwen.providers import schema_pack_context
from memrise.ports.ids import IdGenerator
from memrise.ports.providers import (
    CompletionProvider,
    EmbeddingProvider,
    ExtractedGraphRelation,
    ExtractedMemoryCandidate,
    ExtractionResult,
)
from memrise.ports.repositories import JobQueue, MemoryStore
from memrise.ports.schema_registry import GraphSchemaRegistry
from memrise.runtime.scope import scope_from_namespace_agent
from memrise.write.extraction_validation import (
    CandidatePromotionDecision,
    ExtractionValidationPolicy,
    embedding_text_for_candidate,
)
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
        id_generator: IdGenerator,
        schema_registry: GraphSchemaRegistry | None = None,
    ) -> None:
        self._store = store
        self._jobs = jobs
        self._completion_provider = completion_provider
        self._embedding_provider = embedding_provider
        self._importance_gate = importance_gate
        self._extraction_validation = ExtractionValidationPolicy()
        self._ids = id_generator
        self._schema_registry = schema_registry or InMemoryGraphSchemaRegistry()

    async def capture_episode(self, episode: Episode) -> tuple[Episode, str | None]:
        outcome = await self._store.save_episode(episode)
        episode = outcome.episode
        if not self._importance_gate.should_extract(episode.content):
            return episode, None
        if not outcome.created:
            job_id = await self._jobs.find_job_id_by_dedupe_key(f"extract:{episode.id}")
            return episode, job_id
        job_id = await self._jobs.enqueue(
            job_type=JobType.EXTRACT_EPISODE,
            payload={"episode_id": episode.id},
            dedupe_key=f"extract:{episode.id}",
        )
        return episode, job_id

    async def extract_episode(self, episode_id: str, now: datetime) -> ExtractionOutcome:
        episode = await self._store.get_episode(episode_id)
        if episode is None:
            return ExtractionOutcome(created_memory_version_ids=[], graph_projection_job_ids=[])

        existing_stages = await self._store.list_candidate_stages_for_episode(episode_id)
        if existing_stages:
            return await self._resume_extraction(episode, existing_stages)

        extraction = await self._completion_provider.extract_memories(
            text=episode.content,
            context=await self._extraction_context(episode),
        )

        decisions = self._extraction_validation.decisions_for_episode(
            extraction=extraction,
            episode_content=episode.content,
        )
        return await self._process_decisions(
            episode=episode,
            extraction_metadata=extraction,
            decisions=decisions,
            now=now,
        )

    async def _resume_extraction(
        self,
        episode: Episode,
        stages: list[MemoryCandidateStage],
    ) -> ExtractionOutcome:
        scope = scope_from_namespace_agent(
            namespace_id=episode.namespace_id,
            agent_id=episode.agent_id,
            user_id=episode.user_id,
            project_id=episode.project_id,
        )
        created: list[str] = []
        graph_jobs: list[str] = []
        pending: list[tuple[MemoryCandidateStage, ExtractedMemoryCandidate]] = []
        for stage in stages:
            if stage.status == CandidateStageStatus.PROMOTED and stage.memory_version_id:
                created.append(stage.memory_version_id)
                continue
            if stage.status in {
                CandidateStageStatus.REJECTED,
                CandidateStageStatus.FAILED,
            }:
                continue
            if stage.status != CandidateStageStatus.STAGED or not stage.candidate:
                continue
            pending.append((stage, ExtractedMemoryCandidate.model_validate(stage.candidate)))

        # Batch all staged embeddings into one provider round trip; a failure here
        # raises before any apply, leaving stages STAGED for a later resume.
        embeddings = await self._embedding_provider.embed_many(
            [embedding_text_for_candidate(candidate) for _, candidate in pending]
        )
        for (stage, candidate), embedding in zip(pending, embeddings, strict=True):
            try:
                apply_outcome = await self._store.apply_candidate(
                    scope=scope,
                    candidate=candidate,
                    source_episode_ids=[episode.id],
                    embedding=embedding,
                )
                version_id, job_id = await self._finalize_candidate_stage(
                    stage_id=stage.id,
                    apply_outcome=apply_outcome,
                    memory=apply_outcome.memory,
                    relations=candidate.graph_relations,
                )
                if version_id is not None:
                    created.append(version_id)
                if job_id is not None:
                    graph_jobs.append(job_id)
            except Exception as exc:
                await self._store.update_candidate_stage(
                    stage.id,
                    status=CandidateStageStatus.FAILED,
                    rejection_reason=f"extraction:{type(exc).__name__}",
                )
                raise
        return ExtractionOutcome(
            created_memory_version_ids=created,
            graph_projection_job_ids=graph_jobs,
        )

    async def _process_decisions(
        self,
        *,
        episode: Episode,
        extraction_metadata: ExtractionResult,
        decisions: list[CandidatePromotionDecision],
        now: datetime,
    ) -> ExtractionOutcome:
        scope = scope_from_namespace_agent(
            namespace_id=episode.namespace_id,
            agent_id=episode.agent_id,
            user_id=episode.user_id,
            project_id=episode.project_id,
        )
        created: list[str] = []
        graph_jobs: list[str] = []
        # Pass 1: persist every candidate stage and collect the promotable ones.
        promotable: list[tuple[str, ExtractedMemoryCandidate]] = []
        for decision in decisions:
            candidate = decision.candidate
            stage_id = await self._store.save_candidate_stage(
                MemoryCandidateStage(
                    id=self._ids.new_id("cand"),
                    episode_id=episode.id,
                    namespace_id=episode.namespace_id,
                    agent_id=episode.agent_id,
                    user_id=episode.user_id,
                    project_id=episode.project_id,
                    candidate_index=decision.candidate_index,
                    schema_version=extraction_metadata.schema_version,
                    model_name=extraction_metadata.model_name,
                    prompt_version=extraction_metadata.prompt_version,
                    classification=extraction_metadata.classification.model_dump(mode="json"),
                    candidate=candidate.model_dump(mode="json") if candidate is not None else {},
                    memory_type=candidate.type.value if candidate is not None else None,
                    subject=candidate.subject if candidate is not None else None,
                    key=candidate.key if candidate is not None else None,
                    evidence_quote=candidate.evidence_quote if candidate is not None else None,
                    status=decision.status,
                    promotion_score=decision.promotion_score,
                    rejection_reason=decision.rejection_reason,
                    created_at=now,
                    updated_at=now,
                )
            )
            if decision.should_promote and candidate is not None:
                promotable.append((stage_id, candidate))

        # Pass 2: one batched embedding round trip for all promotable candidates.
        embeddings = await self._embedding_provider.embed_many(
            [embedding_text_for_candidate(candidate) for _, candidate in promotable]
        )
        # Pass 3: apply each with its embedding, failing its own stage on error.
        for (stage_id, candidate), embedding in zip(promotable, embeddings, strict=True):
            try:
                apply_outcome = await self._store.apply_candidate(
                    scope=scope,
                    candidate=candidate,
                    source_episode_ids=[episode.id],
                    embedding=embedding,
                )
                version_id, job_id = await self._finalize_candidate_stage(
                    stage_id=stage_id,
                    apply_outcome=apply_outcome,
                    memory=apply_outcome.memory,
                    relations=candidate.graph_relations,
                )
                if version_id is not None:
                    created.append(version_id)
                if job_id is not None:
                    graph_jobs.append(job_id)
            except Exception as exc:
                await self._store.update_candidate_stage(
                    stage_id,
                    status=CandidateStageStatus.FAILED,
                    rejection_reason=f"extraction:{type(exc).__name__}",
                )
                raise
        return ExtractionOutcome(
            created_memory_version_ids=created,
            graph_projection_job_ids=graph_jobs,
        )

    async def _extraction_context(self, episode: Episode) -> dict[str, object]:
        routes = await route_schema_packs(
            self._schema_registry,
            namespace_id=episode.namespace_id,
            project_id=episode.project_id,
            text=episode.content,
        )
        return {
            "namespace_id": episode.namespace_id,
            "agent_id": episode.agent_id,
            "session_id": episode.session_id,
            "project_id": episode.project_id,
            "active_schema_packs": schema_pack_context([route.pack for route in routes]),
        }

    async def _finalize_candidate_stage(
        self,
        *,
        stage_id: str,
        apply_outcome: ApplyCandidateOutcome,
        memory: CanonicalMemory | None,
        relations: list[ExtractedGraphRelation],
    ) -> tuple[str | None, str | None]:
        if memory is None:
            stage = await self._store.get_candidate_stage(stage_id)
            if stage is not None and stage.status == CandidateStageStatus.PROMOTED:
                return stage.memory_version_id, None
            await self._store.update_candidate_stage(
                stage_id,
                status=CandidateStageStatus.REJECTED,
                rejection_reason=apply_outcome.skip_reason or "candidate:no_memory_applied",
            )
            return None, None
        await self._store.update_candidate_stage(
            stage_id,
            status=CandidateStageStatus.PROMOTED,
            memory_version_id=memory.version.id,
        )
        job_id = await self._store.schedule_graph_projection(
            memory=memory,
            relations=relations,
        )
        return memory.version.id, job_id
