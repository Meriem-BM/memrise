from dataclasses import dataclass
from datetime import datetime

from memrise.ports.graph_repository import GraphRepository
from memrise.ports.graph_store import GraphClaimStore
from memrise.ports.repositories import MemoryStore

USEFULNESS_NEUTRAL = 0.5
# Usefulness decays toward neutral; memories must earn their rank through use.
DEFAULT_USEFULNESS_HALF_LIFE_DAYS = 30.0
# Skip rows touched more recently than this so decay runs are cheap no-ops.
DECAY_MIN_ELAPSED_SECONDS = 86_400
# A contested pair resolves once one side leads by this much usefulness+confidence.
CONTESTED_RESOLUTION_MARGIN = 0.15
# Harmful feedback that drives usefulness this low expires the version outright.
HARMFUL_ARCHIVE_THRESHOLD = 0.05


def decayed_usefulness(
    current: float,
    *,
    elapsed_seconds: float,
    half_life_days: float,
) -> float:
    if elapsed_seconds <= 0 or half_life_days <= 0:
        return current
    factor = 0.5 ** (elapsed_seconds / (half_life_days * 86_400))
    return USEFULNESS_NEUTRAL + (current - USEFULNESS_NEUTRAL) * factor


@dataclass(frozen=True, slots=True)
class LifecycleResult:
    expired_memory_versions: int
    decayed_versions: int
    resolved_contested: int
    expired_claims: int
    expired_edges: int


class LifecycleService:
    """Periodic memory hygiene: expiry, usefulness decay, contested resolution.

    Runs as the EXPIRE_MEMORIES background job; every step is idempotent so
    overlapping or repeated runs are safe.
    """

    def __init__(
        self,
        *,
        store: MemoryStore,
        claim_store: GraphClaimStore | None = None,
        graph_repository: GraphRepository | None = None,
        half_life_days: float = DEFAULT_USEFULNESS_HALF_LIFE_DAYS,
    ) -> None:
        self._store = store
        self._claim_store = claim_store
        self._graph_repository = graph_repository
        self._half_life_days = half_life_days

    async def run(self, now: datetime) -> LifecycleResult:
        expired = await self._store.expire_due_memories(now=now)
        decayed = await self._store.decay_usefulness(
            now=now,
            half_life_days=self._half_life_days,
            min_elapsed_seconds=DECAY_MIN_ELAPSED_SECONDS,
        )
        resolved = await self._store.resolve_contested(
            now=now,
            margin=CONTESTED_RESOLUTION_MARGIN,
        )
        expired_claims = 0
        if self._claim_store is not None:
            expired_claims = await self._claim_store.expire_due_claims(now=now)
        expired_edges = 0
        if self._graph_repository is not None and await self._graph_repository.is_available():
            expired_edges = await self._graph_repository.expire_due_edges(now=now)
        return LifecycleResult(
            expired_memory_versions=expired,
            decayed_versions=decayed,
            resolved_contested=resolved,
            expired_claims=expired_claims,
            expired_edges=expired_edges,
        )
