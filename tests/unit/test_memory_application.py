from tests.mocks.memory_store import MemoryStoreStub, make_memory

from memrise.core.enums import Criticality, MemoryStatus, MemoryType
from memrise.core.models import Scope
from memrise.ports.providers import ExtractedMemoryCandidate


def _scope() -> Scope:
    return Scope(namespace_id="ns", agent_id="agent", user_id="user", project_id="atlas")


def _candidate(*, content: str, value: str, evidence_quote: str) -> ExtractedMemoryCandidate:
    return ExtractedMemoryCandidate(
        type=MemoryType.DECISION,
        subject="Atlas",
        key="package_manager",
        content=content,
        structured_value={"value": value},
        confidence=0.9,
        importance=0.8,
        criticality=Criticality.NORMAL,
        evidence_quote=evidence_quote,
    )


async def test_apply_candidate_supersedes_active_memory_without_deleting_history() -> None:
    store = MemoryStoreStub(
        memories=[
            make_memory(
                memory_id="mem_package_manager",
                version_id="memv_npm",
                content="Atlas uses npm as the package manager.",
                structured_value={"value": "npm"},
            )
        ]
    )

    outcome = await store.apply_candidate(
        scope=_scope(),
        candidate=_candidate(
            content="Atlas uses pnpm as the package manager.",
            value="pnpm",
            evidence_quote="Atlas used npm before, but now uses pnpm.",
        ),
        source_episode_ids=["episode_change"],
        embedding=[0.1, 0.2, 0.3],
    )
    created = outcome.memory

    assert created is not None
    assert created.identity.id == "mem_package_manager"
    assert created.version.status == MemoryStatus.ACTIVE
    assert created.version.supersedes_version_id == "memv_npm"
    history = await store.list_memory_history("mem_package_manager")
    assert len(history) == 2
    old = next(memory for memory in history if memory.version.id == "memv_npm")
    assert old.version.status == MemoryStatus.SUPERSEDED
    assert old.version.valid_until is not None
    assert old.version.superseded_by_version_id == created.version.id


async def test_apply_candidate_does_not_recreate_superseded_duplicate() -> None:
    store = MemoryStoreStub(
        memories=[
            make_memory(
                memory_id="mem_package_manager",
                version_id="memv_npm",
                content="Atlas uses npm as the package manager.",
                structured_value={"value": "npm"},
                status=MemoryStatus.SUPERSEDED,
            )
        ]
    )

    outcome = await store.apply_candidate(
        scope=_scope(),
        candidate=_candidate(
            content="Atlas uses npm as the package manager.",
            value="npm",
            evidence_quote="Atlas uses npm as the package manager.",
        ),
        source_episode_ids=["episode_stale"],
        embedding=[0.1, 0.2, 0.3],
    )

    assert outcome.memory is None
    assert outcome.skip_reason is not None
    history = await store.list_memory_history("mem_package_manager")
    assert len(history) == 1
    assert history[0].version.status == MemoryStatus.SUPERSEDED


async def test_apply_candidate_drops_repeated_historical_value_when_newer_value_is_active() -> None:
    store = MemoryStoreStub(
        memories=[
            make_memory(
                memory_id="mem_package_manager",
                version_id="memv_npm",
                content="Atlas uses npm as the package manager.",
                structured_value={"value": "npm"},
                status=MemoryStatus.SUPERSEDED,
                version_number=1,
            ),
            make_memory(
                memory_id="mem_package_manager",
                version_id="memv_pnpm",
                content="Atlas uses pnpm as the package manager.",
                structured_value={"value": "pnpm"},
                status=MemoryStatus.ACTIVE,
                version_number=2,
                supersedes_version_id="memv_npm",
            ),
        ]
    )

    outcome = await store.apply_candidate(
        scope=_scope(),
        candidate=_candidate(
            content="Atlas uses npm as the package manager.",
            value="npm",
            evidence_quote="Atlas uses npm as the package manager.",
        ),
        source_episode_ids=["episode_stale"],
        embedding=[0.1, 0.2, 0.3],
    )

    assert outcome.memory is None
    assert outcome.skip_reason == "reconcile:historical_duplicate"
    history = await store.list_memory_history("mem_package_manager")
    assert len(history) == 2
    active = await store.find_current_memory(
        scope=_scope(),
        subject="Atlas",
        key="package_manager",
    )
    assert active is not None
    assert active.version.id == "memv_pnpm"
