from fastapi import APIRouter, Query, status

from memrise.schemas.requests import CaptureRequest
from memrise.schemas.responses import CandidateStageSummary, CaptureResponse, EpisodeSummary
from memrise_api.dependencies import MemoryDep

router = APIRouter(prefix="/v1/episodes", tags=["episodes"])


@router.post("", response_model=CaptureResponse, status_code=status.HTTP_202_ACCEPTED)
async def capture_episode(request: CaptureRequest, memory: MemoryDep) -> CaptureResponse:
    return await memory.capture(**request.model_dump())


@router.get("", response_model=list[EpisodeSummary])
async def list_session_episodes(
    memory: MemoryDep,
    namespace_id: str = Query(...),
    agent_id: str = Query(...),
    session_id: str = Query(...),
) -> list[EpisodeSummary]:
    return await memory.list_session_episodes(
        namespace_id=namespace_id,
        agent_id=agent_id,
        session_id=session_id,
    )


@router.get("/{episode_id}/candidates", response_model=list[CandidateStageSummary])
async def list_episode_candidates(
    episode_id: str,
    memory: MemoryDep,
) -> list[CandidateStageSummary]:
    return await memory.list_episode_candidates(episode_id)
