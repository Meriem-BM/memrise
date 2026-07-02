from dataclasses import dataclass

from memrise.core.enums import FeedbackOutcome, FeedbackSource

SOURCE_CONFIDENCE: dict[FeedbackSource, float] = {
    FeedbackSource.USER: 1.0,
    FeedbackSource.DEVELOPER: 1.0,
    FeedbackSource.EVALUATOR: 1.0,
    FeedbackSource.TOOL: 0.8,
    FeedbackSource.AGENT: 0.4,
}


OUTCOME_DELTAS: dict[FeedbackOutcome, float] = {
    FeedbackOutcome.HELPFUL: 0.08,
    FeedbackOutcome.UNUSED: -0.02,
    FeedbackOutcome.HARMFUL: -0.20,
}


def clamp_usefulness(value: float) -> float:
    return min(1.0, max(0.0, value))


@dataclass(frozen=True, slots=True)
class DefaultFeedbackPolicy:
    def confidence_for(self, source: FeedbackSource, provided: float | None) -> float:
        base = SOURCE_CONFIDENCE[source]
        if provided is None:
            return base
        return min(base, max(0.0, provided))

    def usefulness_delta(self, outcome: FeedbackOutcome, confidence: float) -> float:
        return OUTCOME_DELTAS[outcome] * confidence
