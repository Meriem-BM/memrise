from fastapi import APIRouter

from memrise.schemas.responses import LifecycleRunResponse
from memrise_api.dependencies import MemoryDep

router = APIRouter(prefix="/v1/lifecycle", tags=["lifecycle"])


@router.post("/run", response_model=LifecycleRunResponse)
async def run_lifecycle(memory: MemoryDep) -> LifecycleRunResponse:
    return await memory.run_lifecycle()
