from fastapi import APIRouter, status

from memrise.schemas.requests import CaptureRequest
from memrise.schemas.responses import CaptureResponse
from memrise_api.dependencies import MemoryDep

router = APIRouter(prefix="/v1/episodes", tags=["episodes"])


@router.post("", response_model=CaptureResponse, status_code=status.HTTP_202_ACCEPTED)
async def capture_episode(request: CaptureRequest, memory: MemoryDep) -> CaptureResponse:
    return await memory.capture(**request.model_dump())
