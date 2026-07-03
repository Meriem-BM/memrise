from dataclasses import dataclass
from datetime import UTC, datetime

from memrise.core.embeddings import cosine_similarity
from memrise.core.enums import MemoryOperation, MemoryStatus
from memrise.core.models import CanonicalMemory, Feedback, Scope
from memrise.learning.policy import clamp_usefulness
from memrise.learning.reconciliation import Reconciler, reconcile_skip_reason_from_text
from memrise.ports.ids import IdGenerator
from memrise.ports.providers import ExtractedMemoryCandidate
from memrise.ports.repositories import FeedbackPolicy

# Above this cosine similarity, a text conflict without an explicit correction is
# treated as a paraphrase of the existing memory rather than a contradiction.
SEMANTIC_EQUIVALENCE_THRESHOLD = 0.9


@dataclass(frozen=True, slots=True)
class ReinforcePlan:
    version_id: str
    usefulness_score: float
    confidence: float
    source_episode_ids: list[str]


@dataclass(frozen=True, slots=True)
class NewVersionPlan:
    memory_id: str | None
    scope: Scope
    candidate: ExtractedMemoryCandidate
    embedding: list[float]
    version_number: int
    supersedes_version_id: str | None
    supersede_existing_version_id: str | None
    supersede_existing_status: MemoryStatus | None
    new_version_status: MemoryStatus
    source_episode_ids: list[str]
    valid_until: datetime | None
    now: datetime


@dataclass(frozen=True, slots=True)
class CandidateApplyPlan:
    reinforce: ReinforcePlan | None = None
    new_version: NewVersionPlan | None = None


class MemoryApplyService:
    def __init__(
        self,
        *,
        reconciler: Reconciler,
        feedback_policy: FeedbackPolicy,
        id_generator: IdGenerator,
    ) -> None:
        self._reconciler = reconciler
        self._feedback_policy = feedback_policy
        self._ids = id_generator

    def plan_candidate(
        self,
        *,
        scope: Scope,
        candidate: ExtractedMemoryCandidate,
        existing: CanonicalMemory | None,
        source_episode_ids: list[str],
        embedding: list[float],
        now: datetime,
    ) -> CandidateApplyPlan | None:
        decision = self._reconciler.decide(candidate=candidate, existing=existing, now=now)
        operation = decision.operation
        if operation == MemoryOperation.CONTEST and _is_paraphrase_of(
            existing=existing,
            candidate=candidate,
            embedding=embedding,
        ):
            operation = MemoryOperation.REINFORCE
        if operation == MemoryOperation.NOOP:
            return None
        if operation == MemoryOperation.REINFORCE and existing is not None:
            return CandidateApplyPlan(
                reinforce=ReinforcePlan(
                    version_id=existing.version.id,
                    usefulness_score=clamp_usefulness(existing.version.usefulness_score + 0.03),
                    confidence=min(1.0, existing.version.confidence + 0.02),
                    source_episode_ids=list(source_episode_ids),
                ),
            )

        valid_until = (
            datetime.fromisoformat(candidate.valid_until).astimezone(UTC)
            if candidate.valid_until
            else None
        )
        if existing is None:
            version_number = 1
            supersedes_version_id = None
            supersede_existing_version_id = None
            supersede_existing_status = None
            memory_id = self._ids.new_id("mem")
        else:
            version_number = existing.version.version_number + 1
            supersedes_version_id = existing.version.id
            supersede_existing_version_id = existing.version.id
            supersede_existing_status = (
                MemoryStatus.CONTESTED
                if operation == MemoryOperation.CONTEST
                else MemoryStatus.SUPERSEDED
            )
            memory_id = existing.identity.id

        new_version_status = (
            MemoryStatus.CONTESTED if operation == MemoryOperation.CONTEST else MemoryStatus.ACTIVE
        )
        return CandidateApplyPlan(
            new_version=NewVersionPlan(
                memory_id=memory_id,
                scope=scope,
                candidate=candidate,
                embedding=embedding,
                version_number=version_number,
                supersedes_version_id=supersedes_version_id,
                supersede_existing_version_id=supersede_existing_version_id,
                supersede_existing_status=supersede_existing_status,
                new_version_status=new_version_status,
                source_episode_ids=list(source_episode_ids),
                valid_until=valid_until,
                now=now,
            ),
        )

    def noop_skip_reason(
        self,
        *,
        candidate: ExtractedMemoryCandidate,
        existing: CanonicalMemory | None,
        now: datetime,
    ) -> str:
        decision = self._reconciler.decide(candidate=candidate, existing=existing, now=now)
        return reconcile_skip_reason_from_text(decision.reason)

    def new_version_id(self) -> str:
        return self._ids.new_id("memv")

    def updated_usefulness_score(self, *, feedback: Feedback, current_score: float) -> float:
        delta = self._feedback_policy.usefulness_delta(feedback.outcome, feedback.confidence)
        return clamp_usefulness(current_score + delta)


def _is_paraphrase_of(
    *,
    existing: CanonicalMemory | None,
    candidate: ExtractedMemoryCandidate,
    embedding: list[float],
) -> bool:
    """Detect implicit paraphrases so restated facts reinforce instead of contest.

    Provider-flagged conflicts (operation_hint=CONTEST) and structured-value
    mismatches are genuine contradictions and are never reclassified.
    """
    if existing is None or existing.version.embedding is None:
        return False
    if candidate.operation_hint == MemoryOperation.CONTEST:
        return False
    if candidate.structured_value and existing.version.structured_value:
        return False
    return (
        cosine_similarity(embedding, existing.version.embedding) >= SEMANTIC_EQUIVALENCE_THRESHOLD
    )
