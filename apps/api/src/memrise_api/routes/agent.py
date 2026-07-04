from fastapi import APIRouter, status

from memrise.schemas.requests import AgentRespondRequest
from memrise.schemas.responses import AgentRespondResponse
from memrise_api.dependencies import MemoryDep

router = APIRouter(prefix="/v1/agent", tags=["agent"])


@router.post("/respond", response_model=AgentRespondResponse, status_code=status.HTTP_201_CREATED)
async def respond(request: AgentRespondRequest, memory: MemoryDep) -> AgentRespondResponse:
    return await memory.respond(**request.model_dump())
