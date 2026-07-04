import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from memrise_api.lifespan import lifespan
from memrise_api.middleware.api_key import api_key_middleware
from memrise_api.middleware.body_limit import body_limit_middleware
from memrise_api.middleware.error_handler import error_handler_middleware
from memrise_api.middleware.request_id import request_id_middleware
from memrise_api.routes import (
    episodes,
    graph,
    health,
    jobs,
    lifecycle,
    memories,
    retrievals,
    sessions,
)
from memrise_api.settings import ApiSettings


def create_app() -> FastAPI:
    app = FastAPI(
        title="Memrise",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.middleware("http")(error_handler_middleware)
    app.middleware("http")(request_id_middleware)
    app.middleware("http")(body_limit_middleware)
    app.middleware("http")(api_key_middleware)
    app.include_router(health.router)
    app.include_router(episodes.router)
    app.include_router(memories.router)
    app.include_router(retrievals.router)
    app.include_router(sessions.router)
    app.include_router(graph.router)
    app.include_router(jobs.router)
    app.include_router(lifecycle.router)

    api_settings = ApiSettings()
    cors_origins = [
        origin.strip() for origin in api_settings.memrise_cors_origins.split(",") if origin.strip()
    ]
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["x-request-id"],
        )

    return app


app = create_app()


def run() -> None:
    uvicorn.run("memrise_api.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()
