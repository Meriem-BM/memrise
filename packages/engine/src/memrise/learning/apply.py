from dataclasses import dataclass
from datetime import UTC, datetime

from memrise.core.enums import MemoryOperation, MemoryStatus
from memrise.core.models import CanonicalMemory, Feedback, Scope
from memrise.learning.policy import clamp_usefulness
from memrise.learning.reconciliation import Reconciler, reconcile_skip_reason_from_text
from memrise.ports.ids import IdGenerator
from memrise.ports.providers import ExtractedMemoryCandidate
from memrise.ports.repositories import FeedbackPolicy


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
        if decision.operation == MemoryOperation.NOOP:
            return None
        if decision.operation == MemoryOperation.REINFORCE and existing is not None:
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
                if decision.operation == MemoryOperation.CONTEST
                else MemoryStatus.SUPERSEDED
            )
            memory_id = existing.identity.id

        new_version_status = (
            MemoryStatus.CONTESTED
            if decision.operation == MemoryOperation.CONTEST
            else MemoryStatus.ACTIVE
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
