from dataclasses import dataclass
from datetime import datetime

from memrise.core.enums import MemoryOperation, MemoryStatus
from memrise.core.models import CanonicalMemory, Scope
from memrise.ports.providers import ExtractedMemoryCandidate


def normalize_lookup(value: str) -> str:
    return " ".join(value.strip().lower().split())


def same_scope(left: Scope, right: Scope) -> bool:
    return (
        left.namespace_id == right.namespace_id
        and left.agent_id == right.agent_id
        and left.user_id == right.user_id
        and left.project_id == right.project_id
    )


@dataclass(frozen=True, slots=True)
class ReconciliationDecision:
    operation: MemoryOperation
    existing: CanonicalMemory | None
    reason: str


class Reconciler:
    def decide(
        self,
        *,
        candidate: ExtractedMemoryCandidate,
        existing: CanonicalMemory | None,
        now: datetime,
    ) -> ReconciliationDecision:
        del now
        if existing is None:
            return ReconciliationDecision(MemoryOperation.ADD, None, "no related active memory")

        if existing.version.status == MemoryStatus.CONTESTED:
            return ReconciliationDecision(
                MemoryOperation.CONTEST,
                existing,
                "existing memory is contested",
            )

        old_content = normalize_lookup(existing.version.content)
        new_content = normalize_lookup(candidate.content)
        if old_content == new_content:
            return ReconciliationDecision(
                MemoryOperation.REINFORCE,
                existing,
                "same subject/key/scope/content",
            )

        if candidate.operation_hint == MemoryOperation.CONTEST:
            return ReconciliationDecision(
                MemoryOperation.CONTEST, existing, "provider detected conflict"
            )

        if candidate.operation_hint == MemoryOperation.NOOP:
            return ReconciliationDecision(MemoryOperation.NOOP, existing, "provider marked noise")

        return ReconciliationDecision(
            MemoryOperation.SUPERSEDE,
            existing,
            "same subject/key/scope with changed content",
        )
