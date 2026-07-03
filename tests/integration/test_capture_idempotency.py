import os

import pytest

from memrise import Memrise
from memrise.core.enums import EpisodeKind

pytestmark = pytest.mark.asyncio


def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL is required for PostgreSQL integration tests")
    return url


async def test_capture_replays_idempotency_key_end_to_end() -> None:
    memory = Memrise.from_env()
    assert memory.store is not None

    payload = {
        "namespace_id": "it-idem",
        "agent_id": "agent",
        "session_id": "session-idem",
        "project_id": "atlas",
        "idempotency_key": "capture-idem-1",
        "events": [
            {
                "kind": EpisodeKind.USER_MESSAGE.value,
                "content": "Atlas uses pnpm for dependencies.",
                "metadata": {},
            }
        ],
    }

    first = await memory.capture(**payload)
    second = await memory.capture(**payload)

    assert first.episode_ids == second.episode_ids
    assert first.job_ids == second.job_ids
    assert len(first.episode_ids) == 1
