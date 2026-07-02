from fastapi import APIRouter, Query

from memrise.schemas.responses import GraphNeighborhoodResponse
from memrise_api.dependencies import MemoryDep

router = APIRouter(prefix="/v1/graph", tags=["graph"])


@router.get("/neighborhood")
async def neighborhood(
    memory: MemoryDep,
    namespace_id: str = Query(...),
    agent_id: str = Query(...),
    query: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    hops: int = Query(default=1, ge=0, le=2),
) -> GraphNeighborhoodResponse:
    return await memory.graph_neighborhood(
        namespace_id=namespace_id,
        agent_id=agent_id,
        user_id=user_id,
        project_id=project_id,
        query=query,
        hops=hops,
    )
