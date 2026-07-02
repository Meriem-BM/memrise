import pytest

from memrise import Memory
from memrise.core.enums import (
    Criticality,
    EpisodeKind,
    FeedbackOutcome,
    FeedbackSource,
    MemoryStatus,
)
from memrise.core.models import Scope

DEMO_EPISODE = (
    "Atlaused npm before, but we now use pnpm. Never edit its generated lockfile manually."
)


@pytest.mark.asyncio
async def test_capture_extract_retrieve_feedback_vertical_slice() -> None:
    memory = Memory.with_in_memory()
    capture = await memory.capture(
        namespace_id="demo",
        agent_id="coding-agent",
        session_id="session-1",
        user_id="user-1",
        project_id="atlas",
        events=[
            {
                "kind": EpisodeKind.USER_MESSAGE,
                "content": DEMO_EPISODE,
                "metadata": {},
            }
        ],
    )
    assert capture.episode_ids
    assert capture.job_ids

    assert await memory.process_job_once()

    install = await memory.retrieve(
        namespace_id="demo",
        agent_id="coding-agent",
        user_id="user-1",
        project_id="atlas",
        query="How should I install dependencies for Atlas?",
        task_type="dependency_install",
        token_budget=800,
        limit=10,
    )
    assert "pnpm" in install.context

    lockfile = await memory.retrieve(
        namespace_id="demo",
        agent_id="coding-agent",
        user_id="user-1",
        project_id="atlas",
        query="Update the Atlas lockfile.",
        task_type="lockfile_update",
        token_budget=800,
        limit=10,
    )
    assert lockfile.critical
    assert lockfile.critical[0].criticality == Criticality.MUST_INCLUDE
    assert "Never edit" in lockfile.context

    returned = install.memories[0]
    before = returned.usefulness_score
    feedback = await memory.feedback(
        install.retrieval_id,
        outcome=FeedbackOutcome.HELPFUL,
        source=FeedbackSource.DEVELOPER,
        memory_version_id=returned.memory_version_id,
    )
    assert feedback.usefulness_score is not None
    assert feedback.usefulness_score > before


@pytest.mark.asyncio
async def test_supersede_keeps_history() -> None:
    memory = Memory.with_in_memory()
    await memory.capture(
        namespace_id="demo",
        agent_id="coding-agent",
        session_id="s1",
        project_id="atlas",
        events=[
            {"kind": "user_message", "content": "Atlas uses npm for dependencies.", "metadata": {}}
        ],
    )
    await memory.process_job_once()
    await memory.capture(
        namespace_id="demo",
        agent_id="coding-agent",
        session_id="s2",
        project_id="atlas",
        events=[
            {
                "kind": "user_message",
                "content": "Atlas now uses pnpm instead of npm.",
                "metadata": {},
            }
        ],
    )
    await memory.process_job_once()
    memories = await memory.store.list_active_memories(
        scope=Scope(
            namespace_id="demo",
            agent_id="coding-agent",
            project_id="atlas",
        )
    )
    package_memory = next(item for item in memories if item.identity.key == "package_manager")
    history = await memory.store.list_memory_history(package_memory.identity.id)
    assert any(item.version.status == MemoryStatus.SUPERSEDED for item in history)
    assert any(
        item.version.status == MemoryStatus.ACTIVE and "pnpm" in item.version.content
        for item in history
    )
