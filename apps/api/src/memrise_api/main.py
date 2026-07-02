import uvicorn
from fastapi import FastAPI

from memrise_api.lifespan import lifespan
from memrise_api.middleware.api_key import api_key_middleware
from memrise_api.middleware.error_handler import error_handler_middleware
from memrise_api.middleware.request_id import request_id_middleware
from memrise_api.routes import episodes, graph, health, memories, retrievals, sessions


def create_app() -> FastAPI:
    app = FastAPI(
        title="Memrise",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.middleware("http")(error_handler_middleware)
    app.middleware("http")(request_id_middleware)
    app.middleware("http")(api_key_middleware)
    app.include_router(health.router)
    app.include_router(episodes.router)
    app.include_router(memories.router)
    app.include_router(retrievals.router)
    app.include_router(sessions.router)
    app.include_router(graph.router)
    return app


app = create_app()


def run() -> None:
    uvicorn.run("memrise_api.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()
