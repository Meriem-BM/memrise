from memrise.core.models import CanonicalMemory, Episode, MemoryCandidateStage
from memrise.schemas.responses import CandidateStageSummary, EpisodeSummary, MemorySummary


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


def episode_to_summary(episode: Episode) -> EpisodeSummary:
    return EpisodeSummary(
        id=episode.id,
        namespace_id=episode.namespace_id,
        agent_id=episode.agent_id,
        session_id=episode.session_id,
        kind=episode.kind,
        content=episode.content,
        user_id=episode.user_id,
        project_id=episode.project_id,
        created_at=episode.created_at,
    )


def candidate_stage_to_summary(
    stage: MemoryCandidateStage, *, memory_id: str | None = None
) -> CandidateStageSummary:
    return CandidateStageSummary(
        id=stage.id,
        episode_id=stage.episode_id,
        candidate_index=stage.candidate_index,
        status=stage.status,
        promotion_score=stage.promotion_score,
        rejection_reason=stage.rejection_reason,
        memory_version_id=stage.memory_version_id,
        memory_id=memory_id,
        memory_type=stage.memory_type,
        subject=stage.subject,
        key=stage.key,
        evidence_quote=stage.evidence_quote,
        classification=dict(stage.classification),
        created_at=stage.created_at,
    )
