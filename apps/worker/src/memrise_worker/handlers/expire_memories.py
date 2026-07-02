from memrise import Memory
from memrise.core.models import BackgroundJob


async def handle_expire_memories(memory: Memory, job: BackgroundJob) -> None:
    del memory, job
