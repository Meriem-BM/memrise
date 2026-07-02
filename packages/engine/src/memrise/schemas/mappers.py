from memrise.core.models import CanonicalMemory
from memrise.schemas.responses import MemorySummary


def memory_to_summary(memory: CanonicalMemory) -> MemorySummary:
    return MemorySummary(
        memory_id=memory.identity.id,
        memory_version_id=memory.version.id,
        type=memory.identity.type,
        subject=memory.identity.subject,
        key=memory.identity.key,
        content=memory.version.content,
        status=memory.version.status,
        criticality=memory.version.criticality,
        usefulness_score=memory.version.usefulness_score,
        created_at=memory.version.created_at,
        valid_until=memory.version.valid_until,
    )
