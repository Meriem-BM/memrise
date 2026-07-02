from dataclasses import asdict

from fastapi import APIRouter, Query

from memrise.core.models import Scope
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
) -> dict[str, object]:
    nodes, edges = await memory.store.list_graph_neighborhood(
        scope=Scope(
            namespace_id=namespace_id, agent_id=agent_id, user_id=user_id, project_id=project_id
        ),
        query=query,
        hops=hops,
    )
    return {
        "nodes": [asdict(node) for node in nodes],
        "edges": [asdict(edge) for edge in edges],
    }
