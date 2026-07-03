from datetime import UTC, datetime, timedelta

from memrise.core.enums import Criticality, MemoryOperation, MemoryStatus, MemoryType
from memrise.learning.reconciliation import Reconciler
from memrise.ports.providers import EvidenceRole, ExtractedMemoryCandidate
from tests.mocks.memory_store import make_memory

NOW = datetime(2026, 7, 3, tzinfo=UTC)


def _candidate(
    *,
    content: str,
    structured_value: dict[str, object] | None = None,
    operation_hint: MemoryOperation | None = None,
    evidence_quote: str | None = None,
    evidence_role: EvidenceRole = EvidenceRole.STATED,
    valid_until: datetime | None = None,
) -> ExtractedMemoryCandidate:
    return ExtractedMemoryCandidate(
        type=MemoryType.DECISION,
        subject="Atlas",
        key="package_manager",
        content=content,
        structured_value=structured_value or {},
        confidence=0.9,
        importance=0.8,
        criticality=Criticality.NORMAL,
        operation_hint=operation_hint,
        valid_until=valid_until.isoformat() if valid_until else None,
        evidence_quote=evidence_quote or content,
        evidence_role=evidence_role,
    )


def test_reconciler_reinforces_duplicate_structured_value() -> None:
    existing = make_memory(
        content="Atlas uses pnpm as the package manager.",
        structured_value={"value": "PNPM"},
    )
    candidate = _candidate(
        content="Use pnpm when installing Atlas dependencies.",
        structured_value={"value": "pnpm"},
    )

    decision = Reconciler().decide(candidate=candidate, existing=existing, now=NOW)

    assert decision.operation == MemoryOperation.REINFORCE


def test_reconciler_supersedes_when_change_is_explicit() -> None:
    existing = make_memory(
        content="Atlas uses npm as the package manager.",
        structured_value={"value": "npm"},
    )
    candidate = _candidate(
        content="Atlas uses pnpm as the package manager.",
        structured_value={"value": "pnpm"},
        evidence_quote="Atlas used npm before, but now uses pnpm.",
    )

    decision = Reconciler().decide(candidate=candidate, existing=existing, now=NOW)

    assert decision.operation == MemoryOperation.SUPERSEDE


def test_reconciler_contests_ambiguous_conflicting_value() -> None:
    existing = make_memory(
        content="Atlas uses pnpm as the package manager.",
        structured_value={"value": "pnpm"},
    )
    candidate = _candidate(
        content="Atlas uses npm as the package manager.",
        structured_value={"value": "npm"},
    )

    decision = Reconciler().decide(candidate=candidate, existing=existing, now=NOW)

    assert decision.operation == MemoryOperation.CONTEST


def test_reconciler_does_not_reactivate_superseded_duplicate() -> None:
    existing = make_memory(
        content="Atlas uses npm as the package manager.",
        structured_value={"value": "npm"},
        status=MemoryStatus.SUPERSEDED,
    )
    candidate = _candidate(
        content="Atlas uses npm as the package manager.",
        structured_value={"value": "npm"},
    )

    decision = Reconciler().decide(candidate=candidate, existing=existing, now=NOW)

    assert decision.operation == MemoryOperation.NOOP


def test_reconciler_rejects_already_expired_candidate() -> None:
    candidate = _candidate(
        content="For this week, Atlas only focuses on API work.",
        valid_until=NOW - timedelta(days=1),
    )

    decision = Reconciler().decide(candidate=candidate, existing=None, now=NOW)

    assert decision.operation == MemoryOperation.NOOP


def test_reconciler_resolves_contested_memory_with_correction() -> None:
    existing = make_memory(
        content="Atlas deploys on AWS.",
        structured_value={"provider": "aws"},
        status=MemoryStatus.CONTESTED,
    )
    candidate = _candidate(
        content="Atlas deploys on Alibaba Cloud.",
        structured_value={"provider": "alibaba cloud"},
        evidence_quote="Correction: Atlas used AWS before, but now deploys on Alibaba Cloud.",
        evidence_role=EvidenceRole.CORRECTED,
    )

    decision = Reconciler().decide(candidate=candidate, existing=existing, now=NOW)

    assert decision.operation == MemoryOperation.SUPERSEDE
