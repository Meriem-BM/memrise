from typing import Annotated

from fastapi import Depends, Request

from memrise import Memory


def get_memory(request: Request) -> Memory:
    return request.app.state.memory


MemoryDep = Annotated[Memory, Depends(get_memory)]
