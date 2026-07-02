from fastapi import APIRouter

from memrise.integrations.postgres.health import check_database_connectivity
from memrise.runtime.settings import MemorySettings
from memrise_api.errors import DependencyUnavailableError

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready() -> dict[str, str]:
    settings = MemorySettings()
    if settings.database_url is None:
        return {"status": "ok", "database": "not_configured"}
    try:
        await check_database_connectivity(settings.database_url)
    except Exception as exc:
        raise DependencyUnavailableError("database unavailable") from exc
    return {"status": "ok", "database": "ok"}
