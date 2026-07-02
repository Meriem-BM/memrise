from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

PUBLIC_PATHS = ("/health/live", "/health/ready", "/openapi.json", "/docs", "/redoc")


async def api_key_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if request.url.path in PUBLIC_PATHS:
        return await call_next(request)
    settings = request.app.state.settings
    expected = settings.memrise_api_key
    provided = request.headers.get("x-api-key")
    if not expected or provided == expected:
        return await call_next(request)
    return JSONResponse(
        status_code=401,
        content={
            "error": {
                "code": "unauthorized",
                "message": "invalid API key",
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )
