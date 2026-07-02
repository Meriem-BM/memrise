from typing import Annotated

from fastapi import Depends, Request

from memrise import Memrise


def get_memory(request: Request) -> Memrise:
    return request.app.state.memory


MemoryDep = Annotated[Memrise, Depends(get_memory)]
