from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from memrise import Memrise
from memrise.runtime.settings import MemorySettings
from memrise_api.settings import ApiSettings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.api_settings = ApiSettings()
    app.state.engine_settings = MemorySettings()
    app.state.settings = app.state.api_settings
    app.state.memory = Memrise.from_env()
    yield
