from memrise import Memory
from memrise.core.models import BackgroundJob


async def handle_consolidate_session(memory: Memory, job: BackgroundJob) -> None:
    del memory, job
