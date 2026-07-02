from memrise import Memory
from memrise.core.models import BackgroundJob


async def handle_extract_episode(memory: Memory, job: BackgroundJob) -> None:
    await memory.process_job(job)
