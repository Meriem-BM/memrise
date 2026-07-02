from fastapi import APIRouter, Query, status

from memrise.schemas.requests import FeedbackRequest
from memrise.schemas.responses import FeedbackResponse, RetrievalDetail, RetrievalTraceSummary
from memrise_api.dependencies import MemoryDep

router = APIRouter(prefix="/v1/retrievals", tags=["retrievals"])


@router.post(
    "/{retrieval_id}/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED
)
async def feedback(
    retrieval_id: str,
    request: FeedbackRequest,
    memory: MemoryDep,
) -> FeedbackResponse:
    return await memory.feedback(retrieval_id, **request.model_dump())


@router.get("/{retrieval_id}")
async def get_retrieval(retrieval_id: str, memory: MemoryDep) -> RetrievalDetail:
    return await memory.get_retrieval(retrieval_id)


@router.get("", response_model=list[RetrievalTraceSummary])
async def list_retrievals(
    memory: MemoryDep,
    namespace_id: str = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[RetrievalTraceSummary]:
    return await memory.list_retrievals(namespace_id=namespace_id, limit=limit)
