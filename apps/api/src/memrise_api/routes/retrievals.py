from dataclasses import asdict

from fastapi import APIRouter, status

from memrise.schemas.requests import FeedbackRequest
from memrise.schemas.responses import FeedbackResponse
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
async def get_retrieval(retrieval_id: str, memory: MemoryDep) -> dict[str, object]:
    items = await memory.store.get_retrieval_items(retrieval_id)
    return {"retrieval_id": retrieval_id, "items": [asdict(item) for item in items]}
