from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from memrise.core.embeddings import cosine_similarity
from memrise.core.enums import (
    CandidateStageStatus,
    Criticality,
    JobStatus,
    JobType,
    MemoryStatus,
    MemoryType,
)
from memrise.core.errors import CandidateStageNotFoundError, IdempotencyConflictError
from memrise.core.models import (
    ApplyCandidateOutcome,
    BackgroundJob,
    CanonicalMemory,
    Episode,
    EpisodeSaveOutcome,
    Feedback,
    MemoryCandidateStage,
    MemoryIdentity,
    MemorySource,
    MemoryVersion,
    RetrievalItem,
    RetrievalTrace,
    Scope,
)
from memrise.core.text import normalize_lookup
from memrise.learning.apply import SEMANTIC_EQUIVALENCE_THRESHOLD, MemoryApplyService
from memrise.learning.lifecycle import HARMFUL_ARCHIVE_THRESHOLD, decayed_usefulness
from memrise.learning.policy import DefaultFeedbackPolicy
from memrise.learning.reconciliation import (
    Reconciler,
    candidate_has_explicit_change,
    same_memory_value,
)
from memrise.ports.ids import IdGenerator
from memrise.ports.providers import (
    EmbeddingVector,
    ExtractedGraphRelation,
    ExtractedMemoryCandidate,
)
from memrise.runtime.ids import UuidGenerator


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _with_version(memory: CanonicalMemory, **changes: object) -> CanonicalMemory:
    return CanonicalMemory(
        identity=memory.identity,
        version=replace(memory.version, **changes),  # type: ignore[arg-type]
    )


def _search_terms(text: str) -> set[str]:
    return {part.strip(".,:;!?()[]{}\"'").lower() for part in text.split() if part.strip()}


def make_memory(
    *,
    memory_id: str = "mem_test",
    version_id: str = "memv_test",
    namespace_id: str = "ns",
    agent_id: str = "agent",
    user_id: str | None = "user",
    project_id: str | None = "atlas",
    subject: str = "Atlas",
    key: str = "package_manager",
    type: MemoryType = MemoryType.FACT,
    content: str = "Atlas uses pnpm for dependencies.",
    confidence: float = 0.9,
    importance: float = 0.7,
    usefulness_score: float = 0.5,
    criticality: Criticality = Criticality.NORMAL,
    status: MemoryStatus = MemoryStatus.ACTIVE,
    version_number: int = 1,
    structured_value: dict[str, object] | None = None,
    applicability: dict[str, object] | None = None,
    valid_until: datetime | None = None,
    supersedes_version_id: str | None = None,
    superseded_by_version_id: str | None = None,
    embedding: list[float] | None = None,
    embedding_model: str | None = None,
) -> CanonicalMemory:
    now = _utc_now()
    identity = MemoryIdentity(
        id=memory_id,
        namespace_id=namespace_id,
        agent_id=agent_id,
        user_id=user_id,
        project_id=project_id,
        type=type,
        subject=subject,
        key=key,
        created_at=now,
    )
    version = MemoryVersion(
        id=version_id,
        memory_id=memory_id,
        version_number=version_number,
        content=content,
        structured_value=structured_value or {},
        applicability=applicability or {},
        status=status,
        confidence=confidence,
        importance=importance,
        criticality=criticality,
        usefulness_score=usefulness_score,
        valid_from=now,
        valid_until=valid_until,
        supersedes_version_id=supersedes_version_id,
        superseded_by_version_id=superseded_by_version_id,
        embedding=embedding,
        embedding_model=embedding_model,
        created_at=now,
    )
    return CanonicalMemory(identity=identity, version=version)


@dataclass
class MemoryStoreStub:
    episodes: dict[str, Episode] = field(default_factory=dict)
    memories: list[CanonicalMemory] = field(default_factory=list)
    sources: dict[str, list[MemorySource]] = field(default_factory=dict)
    retrieval_traces: dict[str, RetrievalTrace] = field(default_factory=dict)
    retrieval_items: dict[str, list[RetrievalItem]] = field(default_factory=dict)
    feedback: list[Feedback] = field(default_factory=list)
    jobs: list[BackgroundJob] = field(default_factory=list)
    graph_projection_jobs: list[str] = field(default_factory=list)
    candidate_stages: dict[str, MemoryCandidateStage] = field(default_factory=dict)
    id_generator: IdGenerator = field(default_factory=UuidGenerator)

    def _apply_service(self) -> MemoryApplyService:
        return MemoryApplyService(
            reconciler=Reconciler(),
            feedback_policy=DefaultFeedbackPolicy(),
            id_generator=self.id_generator,
        )

    async def save_episode(self, episode: Episode) -> EpisodeSaveOutcome:
        if episode.idempotency_key is not None:
            for existing in self.episodes.values():
                if (
                    existing.namespace_id == episode.namespace_id
                    and existing.idempotency_key == episode.idempotency_key
                ):
                    if (
                        existing.kind != episode.kind
                        or existing.content != episode.content
                        or existing.agent_id != episode.agent_id
                        or existing.session_id != episode.session_id
                        or existing.user_id != episode.user_id
                        or existing.project_id != episode.project_id
                        or existing.metadata != episode.metadata
                    ):
                        msg = (
                            "idempotency key already used with a different capture payload: "
                            f"{episode.idempotency_key!r}"
                        )
                        raise IdempotencyConflictError(msg)
                    return EpisodeSaveOutcome(episode=existing, created=False)
        if episode.id in self.episodes:
            return EpisodeSaveOutcome(episode=self.episodes[episode.id], created=False)
        self.episodes[episode.id] = episode
        return EpisodeSaveOutcome(episode=episode, created=True)

    async def get_episode(self, episode_id: str) -> Episode | None:
        return self.episodes.get(episode_id)

    async def list_session_episodes(
        self,
        *,
        namespace_id: str,
        agent_id: str,
        session_id: str,
    ) -> list[Episode]:
        return [
            episode
            for episode in self.episodes.values()
            if episode.namespace_id == namespace_id
            and episode.agent_id == agent_id
            and episode.session_id == session_id
        ]

    async def list_active_memories(
        self,
        *,
        scope: Scope,
        include_contested: bool = False,
        user_id_is_wildcard: bool = False,
        project_id_is_wildcard: bool = False,
    ) -> list[CanonicalMemory]:
        statuses = {MemoryStatus.ACTIVE}
        if include_contested:
            statuses.add(MemoryStatus.CONTESTED)
        now = _utc_now()
        results: list[CanonicalMemory] = []
        for memory in self.memories:
            identity = memory.identity
            if identity.namespace_id != scope.namespace_id or identity.agent_id != scope.agent_id:
                continue
            if (
                not user_id_is_wildcard
                and scope.user_id is not None
                and identity.user_id != scope.user_id
            ):
                continue
            if (
                not project_id_is_wildcard
                and scope.project_id is not None
                and identity.project_id != scope.project_id
            ):
                continue
            if memory.version.status not in statuses:
                continue
            if memory.version.valid_until is not None and memory.version.valid_until <= now:
                continue
            if memory.version.valid_from > now:
                continue
            if memory.version.status in statuses:
                results.append(memory)
        return results

    async def expire_due_memories(self, *, now: datetime) -> int:
        expired = 0
        updated: list[CanonicalMemory] = []
        for memory in self.memories:
            version = memory.version
            if (
                version.status in (MemoryStatus.ACTIVE, MemoryStatus.CONTESTED)
                and version.valid_until is not None
                and version.valid_until <= now
            ):
                updated.append(_with_version(memory, status=MemoryStatus.EXPIRED))
                expired += 1
            else:
                updated.append(memory)
        self.memories = updated
        return expired

    async def decay_usefulness(
        self,
        *,
        now: datetime,
        half_life_days: float,
        min_elapsed_seconds: int,
    ) -> int:
        decayed = 0
        updated: list[CanonicalMemory] = []
        for memory in self.memories:
            version = memory.version
            elapsed = (now - version.created_at).total_seconds()
            if (
                version.status in (MemoryStatus.ACTIVE, MemoryStatus.CONTESTED)
                and elapsed >= min_elapsed_seconds
                and abs(version.usefulness_score - 0.5) > 0.0001
            ):
                score = decayed_usefulness(
                    version.usefulness_score,
                    elapsed_seconds=elapsed,
                    half_life_days=half_life_days,
                )
                updated.append(_with_version(memory, usefulness_score=score))
                decayed += 1
            else:
                updated.append(memory)
        self.memories = updated
        return decayed

    async def resolve_contested(self, *, now: datetime, margin: float) -> int:
        contested_by_memory: dict[str, list[CanonicalMemory]] = {}
        for memory in self.memories:
            if memory.version.status == MemoryStatus.CONTESTED:
                contested_by_memory.setdefault(memory.identity.id, []).append(memory)
        resolved = 0
        for versions in contested_by_memory.values():
            if len(versions) < 2:
                continue
            versions.sort(key=lambda item: item.version.version_number)
            loser, winner = sorted(
                versions[-2:],
                key=lambda item: item.version.usefulness_score + item.version.confidence,
            )
            gap = (winner.version.usefulness_score + winner.version.confidence) - (
                loser.version.usefulness_score + loser.version.confidence
            )
            if gap < margin:
                continue
            self._replace_version(_with_version(winner, status=MemoryStatus.ACTIVE))
            self._replace_version(
                _with_version(
                    loser,
                    status=MemoryStatus.SUPERSEDED,
                    superseded_by_version_id=winner.version.id,
                )
            )
            resolved += 1
        return resolved

    def _replace_version(self, memory: CanonicalMemory) -> None:
        self.memories = [
            memory if item.version.id == memory.version.id else item for item in self.memories
        ]

    async def list_critical_memories(
        self,
        *,
        scope: Scope,
        limit: int,
    ) -> list[CanonicalMemory]:
        critical = [
            memory
            for memory in self._live_scope_memories(scope)
            if memory.version.criticality == Criticality.MUST_INCLUDE
        ]
        critical.sort(
            key=lambda memory: memory.version.usefulness_score + memory.version.confidence,
            reverse=True,
        )
        return critical[:limit]

    async def search_structured(
        self,
        *,
        scope: Scope,
        query: str,
        limit: int,
    ) -> list[CanonicalMemory]:
        query_terms = _search_terms(query)
        if not query_terms:
            return []
        matches = [
            memory
            for memory in self._live_scope_memories(scope)
            if any(
                term in f"{memory.identity.subject} {memory.identity.key}".lower()
                for term in query_terms
            )
        ]
        matches.sort(
            key=lambda memory: memory.version.usefulness_score + memory.version.confidence,
            reverse=True,
        )
        return matches[:limit]

    async def get_memories_by_version_ids(
        self,
        *,
        scope: Scope,
        version_ids: list[str],
    ) -> list[CanonicalMemory]:
        wanted = set(version_ids)
        return [
            memory for memory in self._live_scope_memories(scope) if memory.version.id in wanted
        ]

    async def search_lexical(
        self,
        *,
        scope: Scope,
        query: str,
        limit: int,
    ) -> list[tuple[CanonicalMemory, float]]:
        query_terms = _search_terms(query)
        scored: list[tuple[CanonicalMemory, float]] = []
        for memory in self._live_scope_memories(scope):
            text = f"{memory.identity.subject} {memory.identity.key} {memory.version.content}"
            terms = _search_terms(text)
            if not query_terms or not (query_terms & terms):
                continue
            scored.append((memory, len(query_terms & terms) / len(query_terms)))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:limit]

    async def search_semantic(
        self,
        *,
        scope: Scope,
        embedding: EmbeddingVector,
        limit: int,
    ) -> list[tuple[CanonicalMemory, float]]:
        if not embedding.values:
            return []
        scored: list[tuple[CanonicalMemory, float]] = []
        for memory in self._live_scope_memories(scope):
            version = memory.version
            if version.embedding is None:
                continue
            if version.embedding_model is not None and version.embedding_model != embedding.model:
                continue
            scored.append((memory, cosine_similarity(embedding.values, version.embedding)))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:limit]

    def _live_scope_memories(self, scope: Scope) -> list[CanonicalMemory]:
        now = _utc_now()
        results: list[CanonicalMemory] = []
        for memory in self.memories:
            identity = memory.identity
            version = memory.version
            if identity.namespace_id != scope.namespace_id or identity.agent_id != scope.agent_id:
                continue
            if identity.user_id is not None and identity.user_id != scope.user_id:
                continue
            if identity.project_id is not None and identity.project_id != scope.project_id:
                continue
            if version.status not in (MemoryStatus.ACTIVE, MemoryStatus.CONTESTED):
                continue
            if version.valid_from > now:
                continue
            if version.valid_until is not None and version.valid_until <= now:
                continue
            results.append(memory)
        return results

    async def list_memory_history(self, memory_id: str) -> list[CanonicalMemory]:
        return [memory for memory in self.memories if memory.identity.id == memory_id]

    async def find_current_memory(
        self,
        *,
        scope: Scope,
        subject: str,
        key: str,
    ) -> CanonicalMemory | None:
        active = await self.list_active_memories(scope=scope, include_contested=True)
        for memory in active:
            if normalize_lookup(memory.identity.subject) == normalize_lookup(
                subject
            ) and normalize_lookup(memory.identity.key) == normalize_lookup(key):
                return memory
        return None

    def _find_semantic_duplicate(
        self,
        *,
        scope: Scope,
        candidate: ExtractedMemoryCandidate,
        embedding: EmbeddingVector,
    ) -> CanonicalMemory | None:
        if not embedding.values:
            return None
        best: CanonicalMemory | None = None
        best_similarity = SEMANTIC_EQUIVALENCE_THRESHOLD
        for memory in self.memories:
            identity = memory.identity
            version = memory.version
            if (
                identity.namespace_id != scope.namespace_id
                or identity.agent_id != scope.agent_id
                or identity.user_id != scope.user_id
                or identity.project_id != scope.project_id
            ):
                continue
            if normalize_lookup(identity.subject) != normalize_lookup(candidate.subject):
                continue
            if normalize_lookup(identity.key) == normalize_lookup(candidate.key):
                continue
            if version.status not in (MemoryStatus.ACTIVE, MemoryStatus.CONTESTED):
                continue
            if version.embedding is None:
                continue
            if version.embedding_model is not None and version.embedding_model != embedding.model:
                continue
            similarity = cosine_similarity(embedding.values, version.embedding)
            if similarity >= best_similarity:
                best = memory
                best_similarity = similarity
        return best

    async def _find_latest_memory(
        self,
        *,
        scope: Scope,
        subject: str,
        key: str,
    ) -> CanonicalMemory | None:
        matches = [
            memory
            for memory in self.memories
            if memory.identity.namespace_id == scope.namespace_id
            and memory.identity.agent_id == scope.agent_id
            and memory.identity.user_id == scope.user_id
            and memory.identity.project_id == scope.project_id
            and normalize_lookup(memory.identity.subject) == normalize_lookup(subject)
            and normalize_lookup(memory.identity.key) == normalize_lookup(key)
        ]
        matches.sort(key=lambda item: item.version.version_number, reverse=True)
        return matches[0] if matches else None

    async def _find_matching_historical_memory(
        self,
        *,
        scope: Scope,
        candidate: ExtractedMemoryCandidate,
    ) -> CanonicalMemory | None:
        for memory in self.memories:
            if memory.version.status not in {
                MemoryStatus.SUPERSEDED,
                MemoryStatus.EXPIRED,
                MemoryStatus.DELETED,
            }:
                continue
            if (
                memory.identity.namespace_id != scope.namespace_id
                or memory.identity.agent_id != scope.agent_id
                or memory.identity.user_id != scope.user_id
                or memory.identity.project_id != scope.project_id
                or normalize_lookup(memory.identity.subject) != normalize_lookup(candidate.subject)
                or normalize_lookup(memory.identity.key) != normalize_lookup(candidate.key)
            ):
                continue
            if same_memory_value(memory, candidate):
                return memory
        return None

    async def apply_candidate(
        self,
        *,
        scope: Scope,
        candidate: ExtractedMemoryCandidate,
        source_episode_ids: list[str],
        embedding: EmbeddingVector,
    ) -> ApplyCandidateOutcome:
        existing = await self.find_current_memory(
            scope=scope,
            subject=candidate.subject,
            key=candidate.key,
        )
        if (
            existing is not None
            and not same_memory_value(existing, candidate)
            and not candidate_has_explicit_change(candidate)
        ):
            historical_duplicate = await self._find_matching_historical_memory(
                scope=scope,
                candidate=candidate,
            )
            if historical_duplicate is not None:
                return ApplyCandidateOutcome(skip_reason="reconcile:historical_duplicate")
        if existing is None:
            existing = self._find_semantic_duplicate(
                scope=scope,
                candidate=candidate,
                embedding=embedding,
            )
        if existing is None:
            existing = await self._find_latest_memory(
                scope=scope,
                subject=candidate.subject,
                key=candidate.key,
            )
        plan = self._apply_service().plan_candidate(
            scope=scope,
            candidate=candidate,
            existing=existing,
            source_episode_ids=source_episode_ids,
            embedding=embedding,
            now=_utc_now(),
        )
        if plan is None:
            return ApplyCandidateOutcome(
                skip_reason=self._apply_service().noop_skip_reason(
                    candidate=candidate,
                    existing=existing,
                    now=_utc_now(),
                ),
            )
        if plan.reinforce is not None and existing is not None:
            updated = _with_version(
                existing,
                confidence=plan.reinforce.confidence,
                usefulness_score=plan.reinforce.usefulness_score,
            )
            self.memories = [
                updated if memory.version.id == existing.version.id else memory
                for memory in self.memories
            ]
            for episode_id in plan.reinforce.source_episode_ids:
                self.sources.setdefault(existing.version.id, []).append(
                    MemorySource(
                        memory_version_id=existing.version.id,
                        episode_id=episode_id,
                        relation="source",
                    )
                )
            return ApplyCandidateOutcome(memory=updated)
        if plan.new_version is None:
            return ApplyCandidateOutcome(skip_reason="reconcile:noop")
        new_version = plan.new_version
        version_id = self._apply_service().new_version_id()
        memory = make_memory(
            memory_id=new_version.memory_id or self.id_generator.new_id("mem"),
            version_id=version_id,
            namespace_id=scope.namespace_id,
            agent_id=scope.agent_id,
            user_id=scope.user_id,
            project_id=scope.project_id,
            subject=new_version.candidate.subject,
            key=new_version.candidate.key,
            type=new_version.candidate.type,
            content=new_version.candidate.content,
            confidence=new_version.candidate.confidence,
            importance=new_version.candidate.importance,
            usefulness_score=0.5,
            criticality=new_version.candidate.criticality,
            status=new_version.new_version_status,
            version_number=new_version.version_number,
            structured_value=dict(new_version.candidate.structured_value),
            applicability=dict(new_version.candidate.applicability),
            valid_until=new_version.valid_until,
            supersedes_version_id=new_version.supersedes_version_id,
            embedding=list(new_version.embedding.values),
            embedding_model=new_version.embedding.model,
        )
        if new_version.supersede_existing_version_id is not None:
            superseded_at = (
                new_version.now
                if new_version.supersede_existing_status == MemoryStatus.SUPERSEDED
                else None
            )
            self.memories = [
                _with_version(
                    item,
                    status=new_version.supersede_existing_status or item.version.status,
                    valid_until=superseded_at or item.version.valid_until,
                    superseded_by_version_id=version_id,
                )
                if item.version.id == new_version.supersede_existing_version_id
                else item
                for item in self.memories
            ]
        self.memories.append(memory)
        for episode_id in new_version.source_episode_ids:
            self.sources.setdefault(memory.version.id, []).append(
                MemorySource(
                    memory_version_id=memory.version.id,
                    episode_id=episode_id,
                    relation="source",
                )
            )
        return ApplyCandidateOutcome(memory=memory)

    async def list_candidate_stages_for_episode(
        self, episode_id: str
    ) -> list[MemoryCandidateStage]:
        stages = [
            stage for stage in self.candidate_stages.values() if stage.episode_id == episode_id
        ]
        stages.sort(key=lambda item: item.candidate_index)
        return stages

    async def get_candidate_stage(self, candidate_stage_id: str) -> MemoryCandidateStage | None:
        return self.candidate_stages.get(candidate_stage_id)

    async def save_candidate_stage(self, stage: MemoryCandidateStage) -> str:
        for existing in self.candidate_stages.values():
            if (
                existing.episode_id == stage.episode_id
                and existing.candidate_index == stage.candidate_index
            ):
                if existing.status == CandidateStageStatus.PROMOTED:
                    self.candidate_stages[existing.id] = replace(
                        stage,
                        id=existing.id,
                        status=existing.status,
                        memory_version_id=existing.memory_version_id,
                        rejection_reason=existing.rejection_reason,
                    )
                else:
                    self.candidate_stages[existing.id] = replace(stage, id=existing.id)
                return existing.id
        self.candidate_stages[stage.id] = stage
        return stage.id

    async def update_candidate_stage(
        self,
        candidate_stage_id: str,
        *,
        status: CandidateStageStatus,
        memory_version_id: str | None = None,
        rejection_reason: str | None = None,
    ) -> None:
        stage = self.candidate_stages.get(candidate_stage_id)
        if stage is None:
            raise CandidateStageNotFoundError(candidate_stage_id)
        self.candidate_stages[candidate_stage_id] = MemoryCandidateStage(
            id=stage.id,
            episode_id=stage.episode_id,
            namespace_id=stage.namespace_id,
            agent_id=stage.agent_id,
            user_id=stage.user_id,
            project_id=stage.project_id,
            candidate_index=stage.candidate_index,
            schema_version=stage.schema_version,
            model_name=stage.model_name,
            prompt_version=stage.prompt_version,
            classification=dict(stage.classification),
            candidate=dict(stage.candidate),
            memory_type=stage.memory_type,
            subject=stage.subject,
            key=stage.key,
            evidence_quote=stage.evidence_quote,
            status=status,
            promotion_score=stage.promotion_score,
            rejection_reason=rejection_reason,
            memory_version_id=memory_version_id,
            created_at=stage.created_at,
            updated_at=_utc_now(),
        )

    async def get_memory_version_by_id(self, memory_version_id: str) -> CanonicalMemory | None:
        for memory in self.memories:
            if memory.version.id == memory_version_id:
                return memory
        return None

    async def schedule_graph_projection(
        self,
        *,
        memory: CanonicalMemory,
        relations: list[ExtractedGraphRelation],
    ) -> str | None:
        if memory.version.status != MemoryStatus.ACTIVE or not relations:
            return None
        job_id = self.id_generator.new_id("job")
        self.graph_projection_jobs.append(job_id)
        self.jobs.append(
            BackgroundJob(
                id=job_id,
                type=JobType.PROJECT_GRAPH,
                payload={
                    "memory_version_id": memory.version.id,
                    "relations": [relation.model_dump() for relation in relations],
                },
                status=JobStatus.PENDING,
                attempts=0,
                max_attempts=3,
                run_at=_utc_now(),
                created_at=_utc_now(),
                updated_at=_utc_now(),
            )
        )
        return job_id

    async def save_retrieval_trace(self, trace: RetrievalTrace, items: list[RetrievalItem]) -> None:
        self.retrieval_traces[trace.id] = trace
        self.retrieval_items[trace.id] = deepcopy(items)

    async def save_feedback(self, feedback: Feedback) -> float | None:
        self.feedback.append(feedback)
        if feedback.memory_version_id is None:
            return None
        memory = await self.get_memory_version_by_id(feedback.memory_version_id)
        if memory is None:
            return None
        delta = DefaultFeedbackPolicy().usefulness_delta(feedback.outcome, feedback.confidence)
        updated_score = min(1.0, max(0.0, memory.version.usefulness_score + delta))
        from memrise.core.enums import FeedbackOutcome

        if (
            feedback.outcome == FeedbackOutcome.HARMFUL
            and updated_score <= HARMFUL_ARCHIVE_THRESHOLD
            and memory.version.status in (MemoryStatus.ACTIVE, MemoryStatus.CONTESTED)
        ):
            self._replace_version(
                _with_version(memory, usefulness_score=updated_score, status=MemoryStatus.EXPIRED)
            )
            return updated_score
        self.memories = [
            _with_version(item, usefulness_score=updated_score)
            if item.version.id == memory.version.id
            else item
            for item in self.memories
        ]
        return updated_score

    async def get_retrieval_items(self, retrieval_id: str) -> list[RetrievalItem]:
        return list(self.retrieval_items.get(retrieval_id, []))

    async def list_memory_sources(self, memory_version_id: str) -> list[MemorySource]:
        return list(self.sources.get(memory_version_id, []))

    async def list_recent_retrievals(
        self, *, namespace_id: str, limit: int
    ) -> list[RetrievalTrace]:
        traces = [
            trace for trace in self.retrieval_traces.values() if trace.namespace_id == namespace_id
        ]
        traces.sort(key=lambda trace: trace.created_at, reverse=True)
        return traces[:limit]


@dataclass
class ExplanationMemoryStore(MemoryStoreStub):
    history_by_memory_id: dict[str, list[CanonicalMemory]] = field(default_factory=dict)
    sources_by_version_id: dict[str, list[MemorySource]] = field(default_factory=dict)

    async def list_memory_history(self, memory_id: str) -> list[CanonicalMemory]:
        return list(self.history_by_memory_id.get(memory_id, []))

    async def list_memory_sources(self, memory_version_id: str) -> list[MemorySource]:
        return list(self.sources_by_version_id.get(memory_version_id, []))
