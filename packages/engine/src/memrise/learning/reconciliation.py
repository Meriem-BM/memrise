import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from memrise.core.enums import MemoryOperation, MemoryStatus
from memrise.core.models import CanonicalMemory
from memrise.core.text import normalize_lookup
from memrise.ports.providers import EvidenceRole, ExtractedMemoryCandidate

_HISTORICAL_STATUSES = {
    MemoryStatus.SUPERSEDED,
    MemoryStatus.EXPIRED,
    MemoryStatus.DELETED,
}

_EXPLICIT_CHANGE_PATTERNS = (
    re.compile(r"\bused to\b", re.IGNORECASE),
    re.compile(r"\bpreviously\b", re.IGNORECASE),
    re.compile(r"\bformerly\b", re.IGNORECASE),
    re.compile(r"\bbefore\b.+\bnow\b", re.IGNORECASE),
    re.compile(r"\bnow\b.+\binstead of\b", re.IGNORECASE),
    re.compile(r"\binstead of\b", re.IGNORECASE),
    re.compile(r"\bno longer\b", re.IGNORECASE),
    re.compile(r"\breplaced?\b", re.IGNORECASE),
    re.compile(r"\bsuperseded?\b", re.IGNORECASE),
    re.compile(r"\bchanged from\b", re.IGNORECASE),
    re.compile(r"\bswitched from\b", re.IGNORECASE),
    re.compile(r"\bmigrated? from\b", re.IGNORECASE),
    re.compile(r"\bcorrection\b", re.IGNORECASE),
    re.compile(r"\bcorrect(?:ed|ion)?\b", re.IGNORECASE),
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
        candidate_expires_at = _candidate_valid_until(candidate)
        if candidate_expires_at is not None and candidate_expires_at <= now:
            return ReconciliationDecision(
                MemoryOperation.NOOP,
                existing,
                "candidate validity interval has already ended",
            )

        if candidate.operation_hint == MemoryOperation.NOOP:
            return ReconciliationDecision(MemoryOperation.NOOP, existing, "provider marked noise")

        if existing is None:
            return ReconciliationDecision(MemoryOperation.ADD, None, "no related active memory")

        same_value = _same_value(existing, candidate)
        existing_status = _effective_status(existing, now)
        explicit_change = _has_explicit_change(candidate)

        if existing_status == MemoryStatus.DELETED:
            return ReconciliationDecision(
                MemoryOperation.NOOP,
                existing,
                "deleted memory is not reactivated by extraction",
            )

        if existing_status in _HISTORICAL_STATUSES:
            if same_value and not explicit_change:
                return ReconciliationDecision(
                    MemoryOperation.NOOP,
                    existing,
                    "candidate repeats historical memory without an explicit current update",
                )
            return ReconciliationDecision(
                MemoryOperation.ADD,
                existing,
                "new current evidence for an existing historical logical memory",
            )

        if existing_status == MemoryStatus.CONTESTED:
            if same_value:
                return ReconciliationDecision(
                    MemoryOperation.REINFORCE,
                    existing,
                    "same value adds evidence to contested memory",
                )
            if explicit_change:
                return ReconciliationDecision(
                    MemoryOperation.SUPERSEDE,
                    existing,
                    "explicit correction resolves contested memory",
                )
            return ReconciliationDecision(
                MemoryOperation.CONTEST,
                existing,
                "existing memory is contested",
            )

        if same_value:
            return ReconciliationDecision(
                MemoryOperation.REINFORCE,
                existing,
                "same subject/key/scope/value",
            )

        if candidate.operation_hint == MemoryOperation.CONTEST:
            return ReconciliationDecision(
                MemoryOperation.CONTEST, existing, "provider detected conflict"
            )

        if explicit_change:
            return ReconciliationDecision(
                MemoryOperation.SUPERSEDE,
                existing,
                "same subject/key/scope with explicit current-state change",
            )

        return ReconciliationDecision(
            MemoryOperation.CONTEST,
            existing,
            "same subject/key/scope with conflicting value but no explicit correction",
        )


def _effective_status(memory: CanonicalMemory, now: datetime) -> MemoryStatus:
    if memory.version.valid_until is not None and memory.version.valid_until <= now:
        return MemoryStatus.EXPIRED
    return memory.version.status


def same_memory_value(memory: CanonicalMemory, candidate: ExtractedMemoryCandidate) -> bool:
    return _same_value(memory, candidate)


def candidate_has_explicit_change(candidate: ExtractedMemoryCandidate) -> bool:
    return _has_explicit_change(candidate)


def reconcile_skip_reason_from_text(reason: str) -> str:
    lowered = reason.lower()
    if "deleted" in lowered:
        return "reconcile:deleted"
    if "historical" in lowered:
        return "reconcile:historical_duplicate"
    return "reconcile:noop"


def _same_value(memory: CanonicalMemory, candidate: ExtractedMemoryCandidate) -> bool:
    old_structured = _canonical_json(memory.version.structured_value)
    new_structured = _canonical_json(candidate.structured_value)
    if old_structured is not None and new_structured is not None:
        return old_structured == new_structured
    return normalize_lookup(memory.version.content) == normalize_lookup(candidate.content)


def _canonical_json(value: dict[str, object]) -> str | None:
    if not value:
        return None
    return json.dumps(_normalize_json(value), sort_keys=True, separators=(",", ":"))


def _normalize_json(value: Any) -> Any:
    if isinstance(value, str):
        return normalize_lookup(value)
    if isinstance(value, dict):
        return {normalize_lookup(str(key)): _normalize_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_json(item) for item in value]
    return value


def _has_explicit_change(candidate: ExtractedMemoryCandidate) -> bool:
    if candidate.operation_hint == MemoryOperation.SUPERSEDE:
        return True
    if candidate.evidence_role == EvidenceRole.CORRECTED:
        return True
    text = f"{candidate.content}\n{candidate.evidence_quote}"
    return any(pattern.search(text) for pattern in _EXPLICIT_CHANGE_PATTERNS)


def _candidate_valid_until(candidate: ExtractedMemoryCandidate) -> datetime | None:
    if candidate.valid_until is None:
        return None
    return datetime.fromisoformat(candidate.valid_until).astimezone(UTC)
