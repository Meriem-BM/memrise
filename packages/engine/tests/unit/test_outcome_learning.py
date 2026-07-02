from memrise.core.enums import FeedbackOutcome, FeedbackSource, MemoryStatus
from memrise.services.outcome_learning import DefaultFeedbackPolicy, clamp_usefulness


def test_helpful_feedback_increases_usefulness() -> None:
    policy = DefaultFeedbackPolicy()
    confidence = policy.confidence_for(FeedbackSource.DEVELOPER, None)
    assert (
        clamp_usefulness(0.5 + policy.usefulness_delta(FeedbackOutcome.HELPFUL, confidence)) > 0.5
    )


def test_harmful_feedback_reduces_usefulness_without_changing_truth_status() -> None:
    policy = DefaultFeedbackPolicy()
    confidence = policy.confidence_for(FeedbackSource.DEVELOPER, None)
    score = clamp_usefulness(0.5 + policy.usefulness_delta(FeedbackOutcome.HARMFUL, confidence))
    assert score < 0.5
    assert MemoryStatus.ACTIVE == MemoryStatus.ACTIVE


def test_critical_constraints_are_not_removed_by_low_usefulness() -> None:
    assert clamp_usefulness(0.01 - 1.0) == 0.0
