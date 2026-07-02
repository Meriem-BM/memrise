from fastapi import APIRouter, Request

from memrise.integrations.postgres.health import check_database_connectivity
from memrise_api.errors import DependencyUnavailableError

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(request: Request) -> dict[str, str]:
    settings = request.app.state.engine_settings
    if settings.database_url is None:
        return {"status": "ok", "database": "not_configured"}
    try:
        details = await check_database_connectivity(settings.database_url)
    except Exception as exc:
        raise DependencyUnavailableError("database unavailable") from exc
    return {"status": "ok", **details}
