from fastapi import APIRouter

from memrise.runtime.memory import to_job_summary
from memrise.schemas.responses import JobSummary
from memrise_api.dependencies import MemoryDep
from memrise_api.errors import NotFoundError

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobSummary)
async def get_job(job_id: str, memory: MemoryDep) -> JobSummary:
    job = await memory.jobs.get_job(job_id)
    if job is None:
        raise NotFoundError("job not found")
    return to_job_summary(job)
