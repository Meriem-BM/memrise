from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

from memrise.core.enums import (
    FeedbackOutcome,
    FeedbackSource,
    GraphEdgeStatus,
    JobStatus,
    JobType,
    MemoryOperation,
    MemoryStatus,
)
from memrise.core.models import (
    BackgroundJob,
    CanonicalMemory,
    Episode,
    Feedback,
    GraphEdge,
    GraphNode,
    MemoryIdentity,
    MemorySource,
    MemoryVersion,
    RetrievalItem,
    RetrievalTrace,
    Scope,
)
from memrise.ports.providers import ExtractedMemoryCandidate
from memrise.services.ids import UuidGenerator
from memrise.services.outcome_learning import DefaultFeedbackPolicy, clamp_usefulness
from memrise.services.reconciliation import Reconciler, normalize_lookup


class InMemoryStore:
    def __init__(self) -> None:
        self._ids = UuidGenerator()
        self._reconciler = Reconciler()
        self._feedback_policy = DefaultFeedbackPolicy()
        self.episodes: dict[str, Episode] = {}
        self.memories: dict[str, MemoryIdentity] = {}
        self.versions: dict[str, MemoryVersion] = {}
        self.sources: list[MemorySource] = []
        self.graph_nodes: dict[str, GraphNode] = {}
        self.graph_edges: dict[str, GraphEdge] = {}
        self.retrieval_traces: dict[str, RetrievalTrace] = {}
        self.retrieval_items: list[RetrievalItem] = []
        self.feedback: dict[str, Feedback] = {}
        self.jobs: dict[str, BackgroundJob] = {}
        self._dedupe_keys: dict[str, str] = {}

    async def save_episode(self, episode: Episode) -> None:
        if episode.id in self.episodes:
            return
        self.episodes[episode.id] = deepcopy(episode)

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
    ) -> list[CanonicalMemory]:
        result: list[CanonicalMemory] = []
        for identity in self.memories.values():
            if not self._scope_applies(identity, scope):
                continue
            current = self._current_version(identity.id, include_contested=include_contested)
            if current is not None:
                result.append(CanonicalMemory(identity=identity, version=current))
        return result

    async def list_memory_history(self, memory_id: str) -> list[CanonicalMemory]:
        identity = self.memories.get(memory_id)
        if identity is None:
            return []
        versions = sorted(
            [version for version in self.versions.values() if version.memory_id == memory_id],
            key=lambda item: item.version_number,
        )
        return [CanonicalMemory(identity=identity, version=version) for version in versions]

    async def find_current_memory(
        self,
        *,
        scope: Scope,
        subject: str,
        key: str,
    ) -> CanonicalMemory | None:
        for identity in self.memories.values():
            identity_scope = Scope(
                namespace_id=identity.namespace_id,
                agent_id=identity.agent_id,
                user_id=identity.user_id,
                project_id=identity.project_id,
            )
            if not self._same_scope(identity_scope, scope):
                continue
            if normalize_lookup(identity.subject) == normalize_lookup(subject) and normalize_lookup(
                identity.key
            ) == normalize_lookup(key):
                version = self._current_version(identity.id, include_contested=True)
                return CanonicalMemory(identity=identity, version=version) if version else None
        return None

    async def apply_candidate(
        self,
        *,
        scope: Scope,
        candidate: ExtractedMemoryCandidate,
        source_episode_ids: list[str],
        embedding: list[float],
    ) -> CanonicalMemory | None:
        now = datetime.now(UTC)
        existing = await self.find_current_memory(
            scope=scope, subject=candidate.subject, key=candidate.key
        )
        decision = self._reconciler.decide(candidate=candidate, existing=existing, now=now)
        if decision.operation == MemoryOperation.NOOP:
            return None
        if decision.operation == MemoryOperation.REINFORCE and existing is not None:
            reinforced = self._replace_version(
                existing.version,
                usefulness_score=clamp_usefulness(existing.version.usefulness_score + 0.03),
                confidence=min(1.0, existing.version.confidence + 0.02),
            )
            self.versions[reinforced.id] = reinforced
            for episode_id in source_episode_ids:
                self.sources.append(
                    MemorySource(
                        memory_version_id=reinforced.id,
                        episode_id=episode_id,
                        relation="reinforced_by",
                    )
                )
            return CanonicalMemory(identity=existing.identity, version=reinforced)

        valid_until = None
        if candidate.valid_until:
            valid_until = datetime.fromisoformat(candidate.valid_until).astimezone(UTC)

        if existing is None:
            identity = MemoryIdentity(
                id=self._ids.new_id("mem"),
                namespace_id=scope.namespace_id,
                agent_id=scope.agent_id,
                user_id=scope.user_id,
                project_id=scope.project_id,
                type=candidate.type,
                subject=candidate.subject,
                key=candidate.key,
                created_at=now,
            )
            self.memories[identity.id] = identity
            version_number = 1
            supersedes_version_id = None
        else:
            identity = existing.identity
            version_number = existing.version.version_number + 1
            supersedes_version_id = existing.version.id
            old_status = (
                MemoryStatus.CONTESTED
                if decision.operation == MemoryOperation.CONTEST
                else MemoryStatus.SUPERSEDED
            )
            superseded = self._replace_version(
                existing.version,
                status=old_status,
                superseded_by_version_id=None,
            )
            self.versions[superseded.id] = superseded

        status = (
            MemoryStatus.CONTESTED
            if decision.operation == MemoryOperation.CONTEST
            else MemoryStatus.ACTIVE
        )
        version = MemoryVersion(
            id=self._ids.new_id("memv"),
            memory_id=identity.id,
            version_number=version_number,
            content=candidate.content,
            structured_value=dict(candidate.structured_value),
            status=status,
            confidence=candidate.confidence,
            importance=candidate.importance,
            criticality=candidate.criticality,
            usefulness_score=0.5,
            valid_from=now,
            valid_until=valid_until,
            supersedes_version_id=supersedes_version_id,
            created_at=now,
            embedding=embedding,
        )
        self.versions[version.id] = version
        if supersedes_version_id:
            old = self.versions[supersedes_version_id]
            self.versions[supersedes_version_id] = self._replace_version(
                old,
                superseded_by_version_id=version.id,
            )
        for episode_id in source_episode_ids:
            self.sources.append(
                MemorySource(
                    memory_version_id=version.id, episode_id=episode_id, relation="derived_from"
                )
            )
        return CanonicalMemory(identity=identity, version=version)

    async def save_graph_projection(
        self,
        *,
        memory: CanonicalMemory,
        relations: list[tuple[str, str, str]],
    ) -> list[GraphEdge]:
        if memory.version.status != MemoryStatus.ACTIVE:
            return []
        edges: list[GraphEdge] = []
        for source, relation, target in relations:
            source_node = self._get_or_create_node(memory, source)
            target_node = self._get_or_create_node(memory, target)
            edge = GraphEdge(
                id=self._ids.new_id("edge"),
                source_node_id=source_node.id,
                target_node_id=target_node.id,
                relation=relation,
                source_memory_version_id=memory.version.id,
                status=GraphEdgeStatus.ACTIVE,
                confidence=memory.version.confidence,
                usefulness_score=memory.version.usefulness_score,
                valid_from=memory.version.valid_from,
                valid_until=memory.version.valid_until,
            )
            self.graph_edges[edge.id] = edge
            edges.append(edge)
        return edges

    async def list_graph_neighborhood(
        self,
        *,
        scope: Scope,
        query: str | None,
        hops: int,
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        del hops
        query_terms = set(normalize_lookup(query or "").split())
        nodes = [
            node
            for node in self.graph_nodes.values()
            if node.namespace_id == scope.namespace_id
            and (scope.project_id is None or node.project_id in (None, scope.project_id))
            and (not query_terms or query_terms & set(node.normalized_name.split()))
        ]
        node_ids = {node.id for node in nodes}
        edges = [
            edge
            for edge in self.graph_edges.values()
            if edge.status == GraphEdgeStatus.ACTIVE
            and (edge.source_node_id in node_ids or edge.target_node_id in node_ids)
        ]
        if not nodes and query_terms:
            edges = [
                edge
                for edge in self.graph_edges.values()
                if edge.status == GraphEdgeStatus.ACTIVE
                and edge.source_memory_version_id in self.versions
            ]
            node_ids = {edge.source_node_id for edge in edges} | {
                edge.target_node_id for edge in edges
            }
            nodes = [node for node in self.graph_nodes.values() if node.id in node_ids]
        return nodes, edges

    async def save_retrieval_trace(
        self,
        trace: RetrievalTrace,
        items: list[RetrievalItem],
    ) -> None:
        self.retrieval_traces[trace.id] = trace
        self.retrieval_items.extend(items)

    async def save_feedback(self, feedback: Feedback) -> float | None:
        self.feedback[feedback.id] = feedback
        if feedback.memory_version_id is None:
            return None
        version = self.versions.get(feedback.memory_version_id)
        if version is None:
            return None
        delta = self._feedback_policy.usefulness_delta(feedback.outcome, feedback.confidence)
        updated_score = clamp_usefulness(version.usefulness_score + delta)
        self.versions[version.id] = self._replace_version(version, usefulness_score=updated_score)
        return updated_score

    async def get_retrieval_items(self, retrieval_id: str) -> list[RetrievalItem]:
        return [item for item in self.retrieval_items if item.retrieval_id == retrieval_id]

    async def list_memory_sources(self, memory_version_id: str) -> list[MemorySource]:
        return [source for source in self.sources if source.memory_version_id == memory_version_id]

    async def list_recent_retrievals(
        self, *, namespace_id: str, limit: int
    ) -> list[RetrievalTrace]:
        traces = [
            trace for trace in self.retrieval_traces.values() if trace.namespace_id == namespace_id
        ]
        return sorted(traces, key=lambda item: item.created_at, reverse=True)[:limit]

    async def enqueue(
        self,
        *,
        job_type: JobType,
        payload: dict[str, object],
        dedupe_key: str | None = None,
    ) -> str:
        if dedupe_key is not None and dedupe_key in self._dedupe_keys:
            return self._dedupe_keys[dedupe_key]
        now = datetime.now(UTC)
        job_id = self._ids.new_id("job")
        job = BackgroundJob(
            id=job_id,
            type=job_type,
            payload=deepcopy(payload),
            status=JobStatus.PENDING,
            attempts=0,
            max_attempts=3,
            run_at=now,
            created_at=now,
            updated_at=now,
        )
        self.jobs[job_id] = job
        if dedupe_key is not None:
            self._dedupe_keys[dedupe_key] = job_id
        return job_id

    async def claim_next(self, *, worker_id: str) -> BackgroundJob | None:
        now = datetime.now(UTC)
        for job in sorted(self.jobs.values(), key=lambda item: item.created_at):
            if job.status not in (JobStatus.PENDING, JobStatus.RETRYABLE):
                continue
            if job.run_at > now:
                continue
            claimed = self._replace_job(
                job,
                status=JobStatus.RUNNING,
                attempts=job.attempts + 1,
                locked_at=now,
                locked_by=worker_id,
                updated_at=now,
            )
            self.jobs[job.id] = claimed
            return claimed
        return None

    async def complete(self, job_id: str) -> None:
        job = self.jobs[job_id]
        now = datetime.now(UTC)
        self.jobs[job_id] = self._replace_job(
            job,
            status=JobStatus.COMPLETED,
            locked_at=None,
            locked_by=None,
            updated_at=now,
        )

    async def fail(self, job_id: str, error: str) -> None:
        job = self.jobs[job_id]
        now = datetime.now(UTC)
        status = JobStatus.FAILED if job.attempts >= job.max_attempts else JobStatus.RETRYABLE
        delay = timedelta(seconds=2 ** max(0, job.attempts - 1))
        self.jobs[job_id] = self._replace_job(
            job,
            status=status,
            locked_at=None,
            locked_by=None,
            last_error=error,
            run_at=now + delay,
            updated_at=now,
        )

    def _scope_applies(self, identity: MemoryIdentity, scope: Scope) -> bool:
        if identity.namespace_id != scope.namespace_id or identity.agent_id != scope.agent_id:
            return False
        if identity.user_id is not None and identity.user_id != scope.user_id:
            return False
        if identity.project_id is not None and identity.project_id != scope.project_id:
            return False
        return True

    def _same_scope(self, left: Scope, right: Scope) -> bool:
        return (
            left.namespace_id == right.namespace_id
            and left.agent_id == right.agent_id
            and left.user_id == right.user_id
            and left.project_id == right.project_id
        )

    def _current_version(self, memory_id: str, *, include_contested: bool) -> MemoryVersion | None:
        candidates = [
            version
            for version in self.versions.values()
            if version.memory_id == memory_id
            and version.status
            in (
                [MemoryStatus.ACTIVE, MemoryStatus.CONTESTED]
                if include_contested
                else [MemoryStatus.ACTIVE]
            )
        ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: item.version_number, reverse=True)[0]

    def _get_or_create_node(self, memory: CanonicalMemory, name: str) -> GraphNode:
        normalized = normalize_lookup(name)
        key = f"{memory.identity.namespace_id}:{memory.identity.project_id}:{normalized}"
        for node in self.graph_nodes.values():
            if f"{node.namespace_id}:{node.project_id}:{node.normalized_name}" == key:
                return node
        node = GraphNode(
            id=self._ids.new_id("node"),
            namespace_id=memory.identity.namespace_id,
            project_id=memory.identity.project_id,
            node_type="entity",
            canonical_name=name,
            normalized_name=normalized,
            aliases=[name],
            metadata={},
        )
        self.graph_nodes[node.id] = node
        return node

    def _replace_version(self, version: MemoryVersion, **changes: Any) -> MemoryVersion:
        data = {
            "id": version.id,
            "memory_id": version.memory_id,
            "version_number": version.version_number,
            "content": version.content,
            "structured_value": version.structured_value,
            "status": version.status,
            "confidence": version.confidence,
            "importance": version.importance,
            "criticality": version.criticality,
            "usefulness_score": version.usefulness_score,
            "valid_from": version.valid_from,
            "valid_until": version.valid_until,
            "supersedes_version_id": version.supersedes_version_id,
            "superseded_by_version_id": version.superseded_by_version_id,
            "created_at": version.created_at,
            "embedding": version.embedding,
        }
        data.update(changes)
        return MemoryVersion(**data)

    def _replace_job(self, job: BackgroundJob, **changes: Any) -> BackgroundJob:
        data = {
            "id": job.id,
            "type": job.type,
            "payload": job.payload,
            "status": job.status,
            "attempts": job.attempts,
            "max_attempts": job.max_attempts,
            "run_at": job.run_at,
            "locked_at": job.locked_at,
            "locked_by": job.locked_by,
            "last_error": job.last_error,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
        }
        data.update(changes)
        return BackgroundJob(**data)


def feedback_from_input(
    *,
    feedback_id: str,
    retrieval_id: str,
    outcome: FeedbackOutcome,
    source: FeedbackSource,
    confidence: float,
    memory_version_id: str | None,
    graph_edge_id: str | None,
    task_type: str | None,
) -> Feedback:
    return Feedback(
        id=feedback_id,
        retrieval_id=retrieval_id,
        outcome=outcome,
        source=source,
        confidence=confidence,
        memory_version_id=memory_version_id,
        graph_edge_id=graph_edge_id,
        task_type=task_type,
        created_at=datetime.now(UTC),
    )
