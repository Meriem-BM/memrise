from memrise.core.enums import FeedbackOutcome, FeedbackSource
from memrise.learning.policy import DefaultFeedbackPolicy, clamp_usefulness


def test_clamp_usefulness_bounds_values() -> None:
    assert clamp_usefulness(-0.2) == 0.0
    assert clamp_usefulness(0.5) == 0.5
    assert clamp_usefulness(1.4) == 1.0


def test_default_feedback_policy_caps_confidence_and_applies_deltas() -> None:
    policy = DefaultFeedbackPolicy()

    assert policy.confidence_for(FeedbackSource.USER, None) == 1.0
    assert policy.confidence_for(FeedbackSource.AGENT, 0.9) == 0.4
    assert policy.confidence_for(FeedbackSource.TOOL, 0.5) == 0.5

    helpful = policy.usefulness_delta(FeedbackOutcome.HELPFUL, confidence=1.0)
    harmful = policy.usefulness_delta(FeedbackOutcome.HARMFUL, confidence=0.5)

    assert helpful == 0.08
    assert harmful == -0.10
