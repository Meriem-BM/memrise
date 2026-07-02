import asyncio

from memrise import Memory

DEMO_EPISODE = (
    "Atlaused npm before, but we now use pnpm. Never edit its generated lockfile manually."
)


async def main() -> None:
    memory = Memory.from_env()
    await memory.capture(
        namespace_id="demo",
        agent_id="coding-agent",
        session_id="session-1",
        user_id="user-1",
        project_id="atlas",
        events=[
            {
                "kind": "user_message",
                "content": DEMO_EPISODE,
                "metadata": {},
            }
        ],
    )
    while await memory.process_job_once("seed-demo"):
        pass


if __name__ == "__main__":
    asyncio.run(main())
