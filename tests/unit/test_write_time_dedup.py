from memrise.core.enums import Criticality, MemoryOperation, MemoryStatus, MemoryType
from memrise.core.models import CanonicalMemory, Scope
from memrise.ports.providers import EmbeddingVector, ExtractedMemoryCandidate
from tests.mocks.memory_store import MemoryStoreStub, make_memory

SCOPE = Scope(namespace_id="ns", agent_id="agent", user_id="user", project_id="atlas")
MODEL = "mock-embedding"


def _existing() -> CanonicalMemory:
    return make_memory(
        memory_id="mem_rule",
        version_id="memv_rule",
        subject="lockfile",
        key="rule",
        content="Never manually edit the generated lockfile.",
        embedding=[1.0, 0.0],
        embedding_model=MODEL,
    )


def _candidate(
    content: str, *, operation_hint: MemoryOperation | None = None
) -> ExtractedMemoryCandidate:
    return ExtractedMemoryCandidate(
        type=MemoryType.CONSTRAINT,
        subject="pnpm_lockfile",  # different subject/key than the existing memory
        key="edit_policy",
        content=content,
        structured_value={},
        confidence=0.9,
        importance=0.8,
        criticality=Criticality.NORMAL,
        operation_hint=operation_hint,
        evidence_quote=content,
    )


async def test_plain_near_duplicate_reinforces_existing_cross_subject() -> None:
    store = MemoryStoreStub(memories=[_existing()])
    outcome = await store.apply_candidate(
        scope=SCOPE,
        candidate=_candidate("Never manually edit the pnpm lockfile."),
        source_episode_ids=[],
        embedding=EmbeddingVector(values=[1.0, 0.0], model=MODEL, dimensions=2),
    )
    # No new logical memory: the existing one is reinforced.
    active = [m for m in store.memories if m.version.status == MemoryStatus.ACTIVE]
    assert len(active) == 1
    assert active[0].identity.id == "mem_rule"
    assert outcome.memory is not None
    assert outcome.memory.identity.id == "mem_rule"


async def test_explicit_change_is_not_hijacked_by_cross_subject_neighbor() -> None:
    store = MemoryStoreStub(memories=[_existing()])
    # Correction intent must land on its own memory, not merge into a neighbor.
    await store.apply_candidate(
        scope=SCOPE,
        candidate=_candidate(
            "We used to allow lockfile edits; now editing is prohibited.",
            operation_hint=MemoryOperation.SUPERSEDE,
        ),
        source_episode_ids=[],
        embedding=EmbeddingVector(values=[1.0, 0.0], model=MODEL, dimensions=2),
    )
    subjects = {
        m.identity.subject for m in store.memories if m.version.status == MemoryStatus.ACTIVE
    }
    assert "pnpm_lockfile" in subjects  # its own memory was created, not merged away
