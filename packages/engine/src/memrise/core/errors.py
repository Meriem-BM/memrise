class IdempotencyConflictError(Exception):
    """Raised when an idempotency key is reused with a different request payload."""


class CandidateStageNotFoundError(Exception):
    def __init__(self, candidate_stage_id: str) -> None:
        self.candidate_stage_id = candidate_stage_id
        super().__init__(f"candidate stage not found: {candidate_stage_id}")
