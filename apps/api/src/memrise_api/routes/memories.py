from fastapi import APIRouter, Query, status

from memrise.core.models import Scope
from memrise.schemas.requests import RetrieveRequest
from memrise.schemas.responses import MemoryExplanation, MemorySummary, RetrieveResponse
from memrise.services.explanation import to_summary
from memrise_api.dependencies import MemoryDep
from memrise_api.errors import NotFoundError

router = APIRouter(prefix="/v1/memories", tags=["memories"])


@router.post("/retrieve", response_model=RetrieveResponse, status_code=status.HTTP_201_CREATED)
async def retrieve(request: RetrieveRequest, memory: MemoryDep) -> RetrieveResponse:
    return await memory.retrieve(**request.model_dump())


@router.get("", response_model=list[MemorySummary])
async def list_memories(
    memory: MemoryDep,
    namespace_id: str = Query(...),
    agent_id: str = Query(...),
    user_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
) -> list[MemorySummary]:
    memories = await memory.store.list_active_memories(
        scope=Scope(
            namespace_id=namespace_id,
            agent_id=agent_id,
            user_id=user_id,
            project_id=project_id,
        )
    )
    return [to_summary(item) for item in memories]


@router.get("/{memory_id}", response_model=MemorySummary)
async def get_memory(memory_id: str, memory: MemoryDep) -> MemorySummary:
    explanation = await memory.explain(memory_id)
    if explanation.current_version is None:
        raise NotFoundError("memory not found")
    return explanation.current_version


@router.get("/{memory_id}/explanation", response_model=MemoryExplanation)
async def explain_memory(memory_id: str, memory: MemoryDep) -> MemoryExplanation:
    explanation = await memory.explain(memory_id)
    if not explanation.versions:
        raise NotFoundError("memory not found")
    return explanation
