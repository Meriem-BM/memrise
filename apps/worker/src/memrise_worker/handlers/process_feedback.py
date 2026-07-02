from memrise import Memory
from memrise.core.models import BackgroundJob


async def handle_process_feedback(memory: Memory, job: BackgroundJob) -> None:
    del memory, job
