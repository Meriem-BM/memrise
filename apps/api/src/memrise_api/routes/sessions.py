from fastapi import APIRouter, status

from memrise.schemas.requests import ConsolidateRequest
from memrise.schemas.responses import ConsolidateResponse
from memrise_api.dependencies import MemoryDep

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


@router.post(
    "/{session_id}/consolidate",
    response_model=ConsolidateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def consolidate(
    session_id: str,
    request: ConsolidateRequest,
    memory: MemoryDep,
) -> ConsolidateResponse:
    data = request.model_dump()
    data["session_id"] = session_id
    return await memory.consolidate(**data)
