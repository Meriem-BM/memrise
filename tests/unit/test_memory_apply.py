from datetime import UTC, datetime

from memrise.core.enums import Criticality, MemoryOperation, MemoryStatus, MemoryType
from memrise.core.models import Scope
from memrise.learning.apply import MemoryApplyService
from memrise.learning.policy import DefaultFeedbackPolicy
from memrise.learning.reconciliation import Reconciler
from memrise.ports.providers import EmbeddingVector, ExtractedMemoryCandidate
from memrise.runtime.ids import UuidGenerator
from tests.mocks.memory_store import make_memory

NOW = datetime(2026, 7, 3, tzinfo=UTC)
SCOPE = Scope(namespace_id="ns", agent_id="agent", user_id="user", project_id="atlas")


def _vector(values: list[float]) -> EmbeddingVector:
    return EmbeddingVector(values=values, model="mock-embedding", dimensions=len(values))


SIMILAR = _vector([1.0, 0.0, 0.05])
DISSIMILAR = _vector([0.0, 1.0, 0.0])
BASE = [1.0, 0.0, 0.0]


def _service() -> MemoryApplyService:
    return MemoryApplyService(
        reconciler=Reconciler(),
        feedback_policy=DefaultFeedbackPolicy(),
        id_generator=UuidGenerator(),
    )


def _candidate(
    *,
    content: str,
    operation_hint: MemoryOperation | None = None,
    structured_value: dict[str, object] | None = None,
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
        evidence_quote=content,
    )


def test_paraphrase_reinforces_instead_of_contesting() -> None:
    existing = make_memory(
        content="Atlas uses pnpm as the package manager.",
        embedding=BASE,
    )
    plan = _service().plan_candidate(
        scope=SCOPE,
        candidate=_candidate(content="pnpm is the package manager for Atlas."),
        existing=existing,
        source_episode_ids=["ep_1"],
        embedding=SIMILAR,
        now=NOW,
    )

    assert plan is not None
    assert plan.reinforce is not None
    assert plan.new_version is None
    assert plan.reinforce.version_id == existing.version.id


def test_dissimilar_conflict_still_contests() -> None:
    existing = make_memory(
        content="Atlas uses pnpm as the package manager.",
        embedding=BASE,
    )
    plan = _service().plan_candidate(
        scope=SCOPE,
        candidate=_candidate(content="Atlas uses npm as the package manager."),
        existing=existing,
        source_episode_ids=["ep_1"],
        embedding=DISSIMILAR,
        now=NOW,
    )

    assert plan is not None
    assert plan.new_version is not None
    assert plan.new_version.new_version_status == MemoryStatus.CONTESTED


def test_provider_flagged_conflict_is_never_reclassified() -> None:
    existing = make_memory(
        content="Atlas uses pnpm as the package manager.",
        embedding=BASE,
    )
    plan = _service().plan_candidate(
        scope=SCOPE,
        candidate=_candidate(
            content="pnpm is the package manager for Atlas.",
            operation_hint=MemoryOperation.CONTEST,
        ),
        existing=existing,
        source_episode_ids=["ep_1"],
        embedding=SIMILAR,
        now=NOW,
    )

    assert plan is not None
    assert plan.new_version is not None
    assert plan.new_version.new_version_status == MemoryStatus.CONTESTED


def test_structured_value_mismatch_is_never_reclassified() -> None:
    existing = make_memory(
        content="Atlas uses pnpm as the package manager.",
        structured_value={"value": "pnpm"},
        embedding=BASE,
    )
    plan = _service().plan_candidate(
        scope=SCOPE,
        candidate=_candidate(
            content="Atlas package manager is npm.",
            structured_value={"value": "npm"},
        ),
        existing=existing,
        source_episode_ids=["ep_1"],
        embedding=SIMILAR,
        now=NOW,
    )

    assert plan is not None
    assert plan.new_version is not None
    assert plan.new_version.new_version_status == MemoryStatus.CONTESTED


def test_missing_existing_embedding_falls_back_to_contest() -> None:
    existing = make_memory(content="Atlas uses pnpm as the package manager.", embedding=None)
    plan = _service().plan_candidate(
        scope=SCOPE,
        candidate=_candidate(content="pnpm is the package manager for Atlas."),
        existing=existing,
        source_episode_ids=["ep_1"],
        embedding=SIMILAR,
        now=NOW,
    )

    assert plan is not None
    assert plan.new_version is not None
    assert plan.new_version.new_version_status == MemoryStatus.CONTESTED
