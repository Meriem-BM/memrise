from datetime import datetime

from memrise.consolidation.dedupe import merge_scope_duplicates
from memrise.core.models import Scope
from memrise.ports.providers import (
    CompletionProvider,
    EmbeddingProvider,
    ExtractedMemoryCandidate,
)
from memrise.ports.repositories import MemoryStore
from memrise.runtime.scope import scope_from_namespace_agent
from memrise.schemas.requests import ConsolidateRequest
from memrise.write.extraction_validation import (
    MIN_EXTRACTED_CONFIDENCE,
    MIN_EXTRACTED_IMPORTANCE,
    contains_secret_like_text,
    embedding_text_for_candidate,
    evidence_quote_matches,
)
from memrise.write.service import WriteService


class SessionConsolidationService:
    """Cross-episode consolidation for one session.

    First guarantees every episode went through per-episode extraction (the
    resume path), then asks the consolidation model for session-level
    synthesis: merged paraphrases, conclusions only visible across episodes,
    and end-of-session corrections. Accepted candidates flow through the same
    apply_candidate pipeline as extraction, so reconciliation, near-duplicate
    detection, and graph projection all still apply.
    """

    def __init__(
        self,
        *,
        store: MemoryStore,
        write: WriteService,
        completion_provider: CompletionProvider,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self._store = store
        self._write = write
        self._completion_provider = completion_provider
        self._embedding_provider = embedding_provider

    async def consolidate_session(self, request: ConsolidateRequest, now: datetime) -> None:
        episodes = await self._store.list_session_episodes(
            namespace_id=request.namespace_id,
            agent_id=request.agent_id,
            session_id=request.session_id,
        )
        if not episodes:
            return
        for episode in episodes:
            await self._write.extract_episode(episode.id, now)

        scope = scope_from_namespace_agent(
            namespace_id=request.namespace_id,
            agent_id=request.agent_id,
            user_id=request.user_id,
            project_id=request.project_id,
        )
        existing = await self._store.list_active_memories(scope=scope, include_contested=True)
        result = await self._completion_provider.consolidate_memories(
            episodes=[
                {"id": episode.id, "kind": episode.kind.value, "content": episode.content}
                for episode in episodes
            ],
            existing_memories=[
                {
                    "subject": memory.identity.subject,
                    "key": memory.identity.key,
                    "type": memory.identity.type.value,
                    "content": memory.version.content,
                    "status": memory.version.status.value,
                }
                for memory in existing
            ],
            context={
                "namespace_id": request.namespace_id,
                "agent_id": request.agent_id,
                "session_id": request.session_id,
                "project_id": request.project_id,
            },
        )

        session_text = "\n".join(episode.content for episode in episodes)
        source_episode_ids = [episode.id for episode in episodes]
        accepted = [
            candidate
            for candidate in result.candidates
            if not _reject_candidate(candidate, session_text=session_text)
        ]
        embeddings = await self._embedding_provider.embed_many(
            [embedding_text_for_candidate(candidate) for candidate in accepted]
        )
        for candidate, embedding in zip(accepted, embeddings, strict=True):
            outcome = await self._store.apply_candidate(
                scope=scope,
                candidate=candidate,
                source_episode_ids=source_episode_ids,
                embedding=embedding,
            )
            if outcome.memory is not None:
                await self._store.schedule_graph_projection(
                    memory=outcome.memory,
                    relations=candidate.graph_relations,
                )

        await self.merge_duplicates(scope=scope, now=now)

    async def merge_duplicates(self, *, scope: Scope, now: datetime) -> int:
        """Collapse near-duplicate active memories into one survivor each.

        Reconciliation only compares a candidate against the single memory sharing
        its subject/key, so restatements under different subjects/keys accumulate as
        separate memories (e.g. three phrasings of the same lockfile rule). This
        semantic pass groups same-scope active memories by embedding similarity and
        supersedes the weaker members into the strongest. Returns how many memories
        were superseded.
        """
        return await merge_scope_duplicates(self._store, scope=scope, now=now)


def _reject_candidate(candidate: ExtractedMemoryCandidate, *, session_text: str) -> bool:
    """Deterministic guardrails: consolidation output gets no more trust than extraction."""
    if candidate.confidence < MIN_EXTRACTED_CONFIDENCE:
        return True
    if candidate.importance < MIN_EXTRACTED_IMPORTANCE:
        return True
    if not evidence_quote_matches(session_text, candidate.evidence_quote):
        return True
    if contains_secret_like_text(f"{candidate.content}\n{candidate.evidence_quote}"):
        return True
    return False
