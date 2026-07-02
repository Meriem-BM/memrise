from datetime import UTC, datetime

from memrise.core.enums import Criticality, MemoryStatus, MemoryType, RetrievalSourceType
from memrise.core.models import CanonicalMemory, MemoryIdentity, MemoryVersion
from memrise.services.retrieval import RetrievalCandidate, reciprocal_rank_fusion


def test_reciprocal_rank_fusion_combines_ranked_sources() -> None:
    now = datetime.now(UTC)
    memory = CanonicalMemory(
        identity=MemoryIdentity(
            id="m1",
            namespace_id="demo",
            agent_id="agent",
            type=MemoryType.FACT,
            subject="Atlas",
            key="package_manager",
            created_at=now,
        ),
        version=MemoryVersion(
            id="v1",
            memory_id="m1",
            version_number=1,
            content="Atlas uses pnpm.",
            structured_value={},
            status=MemoryStatus.ACTIVE,
            confidence=1.0,
            importance=1.0,
            criticality=Criticality.NORMAL,
            usefulness_score=0.5,
            valid_from=now,
            created_at=now,
        ),
    )
    candidate = RetrievalCandidate(memory, RetrievalSourceType.LEXICAL, 1, 1.0)
    scores = reciprocal_rank_fusion([candidate])
    assert scores["v1"] > 0
