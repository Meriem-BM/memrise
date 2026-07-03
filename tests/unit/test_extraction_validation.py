from memrise.core.enums import CandidateStageStatus, Criticality, MemoryType
from memrise.ports.providers import (
    EpisodeClassification,
    EpisodeDurability,
    ExtractedMemoryCandidate,
    ExtractionResult,
    KnowledgeClass,
    Sensitivity,
)
from memrise.write.extraction_validation import (
    ExtractionValidationPolicy,
    embedding_text_for_candidate,
    promotion_score_for_candidate,
)


def _candidate(**overrides: object) -> ExtractedMemoryCandidate:
    values = {
        "type": MemoryType.DECISION,
        "subject": "Atlas",
        "key": "package_manager",
        "content": "Atlas uses pnpm as its package manager.",
        "structured_value": {"value": "pnpm"},
        "confidence": 0.9,
        "importance": 0.8,
        "criticality": Criticality.NORMAL,
        "evidence_quote": "Atlas used npm before, but now it uses pnpm.",
    }
    values.update(overrides)
    return ExtractedMemoryCandidate.model_validate(values)


def _result(
    *,
    classification: EpisodeClassification,
    candidates: list[ExtractedMemoryCandidate] | None = None,
) -> ExtractionResult:
    return ExtractionResult(
        classification=classification,
        candidates=candidates or [],
        model_name="test-model",
        prompt_version="memory_extraction_v1",
    )


def _classification(
    *,
    should_extract: bool = True,
    durability: EpisodeDurability = EpisodeDurability.DURABLE,
    sensitivity: Sensitivity = Sensitivity.NORMAL,
) -> EpisodeClassification:
    return EpisodeClassification(
        should_extract=should_extract,
        durability=durability,
        knowledge_classes=[KnowledgeClass.DECISION],
        reason_codes=["test"],
        sensitivity=sensitivity,
    )


def test_noise_classification_produces_no_candidates() -> None:
    extraction = _result(
        classification=_classification(
            should_extract=False,
            durability=EpisodeDurability.NONE,
        ),
        candidates=[_candidate()],
    )

    accepted = ExtractionValidationPolicy().candidates_for_episode(
        extraction=extraction,
        episode_content="Atlas used npm before, but now it uses pnpm.",
    )

    assert accepted == []


def test_candidate_must_quote_episode_evidence() -> None:
    extraction = _result(
        classification=_classification(),
        candidates=[_candidate(evidence_quote="This quote is not in the episode.")],
    )

    accepted = ExtractionValidationPolicy().candidates_for_episode(
        extraction=extraction,
        episode_content="Atlas used npm before, but now it uses pnpm.",
    )

    assert accepted == []


def test_low_importance_candidate_records_rejection_reason() -> None:
    candidate = _candidate(importance=0.01)
    extraction = _result(classification=_classification(), candidates=[candidate])

    decisions = ExtractionValidationPolicy().decisions_for_episode(
        extraction=extraction,
        episode_content="Atlas used npm before, but now it uses pnpm.",
    )

    assert decisions[0].status == CandidateStageStatus.REJECTED
    assert decisions[0].rejection_reason == "candidate:low_importance"


def test_promotion_score_rewards_critical_durable_evidence() -> None:
    normal = _candidate(confidence=0.7, importance=0.4)
    critical = _candidate(
        confidence=0.7,
        importance=0.4,
        criticality=Criticality.MUST_INCLUDE,
    )

    assert promotion_score_for_candidate(
        candidate=critical,
        durability=EpisodeDurability.DURABLE,
    ) > promotion_score_for_candidate(
        candidate=normal,
        durability=EpisodeDurability.DURABLE,
    )


def test_secret_classification_is_never_promoted() -> None:
    extraction = _result(
        classification=_classification(sensitivity=Sensitivity.SECRET),
        candidates=[_candidate(content="The API token is secret.", evidence_quote="token=abc123")],
    )

    accepted = ExtractionValidationPolicy().candidates_for_episode(
        extraction=extraction,
        episode_content="token=abc123",
    )

    assert accepted == []


def test_embedding_text_uses_candidate_hint_or_canonical_context() -> None:
    candidate = _candidate(embedding_text="Project Atlas package manager decision: pnpm")
    fallback = _candidate(embedding_text=None)

    assert embedding_text_for_candidate(candidate) == "Project Atlas package manager decision: pnpm"
    assert embedding_text_for_candidate(fallback) == (
        "Atlas package_manager: Atlas uses pnpm as its package manager."
    )
