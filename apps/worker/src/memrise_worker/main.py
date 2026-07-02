import asyncio
import logging
import signal

from memrise import Memory
from memrise.runtime.settings import MemorySettings
from memrise_worker.runner import WorkerRunner


async def amain() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = MemorySettings()
    runner = WorkerRunner(memory=Memory.from_env(), settings=settings)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)
    await runner.run_forever(stop_event)


def run() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    run()
