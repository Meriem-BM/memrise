from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from memrise import Memory
from memrise.runtime.settings import MemorySettings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = MemorySettings()
    app.state.settings = settings
    app.state.memory = Memory.from_env()
    yield
