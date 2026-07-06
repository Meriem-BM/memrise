from collections.abc import Awaitable, Callable
from hmac import compare_digest

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

PUBLIC_PATHS = ("/health/live", "/health/ready", "/openapi.json", "/docs", "/redoc")


async def api_key_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if request.url.path in PUBLIC_PATHS:
        return await call_next(request)
    settings = request.app.state.api_settings
    if settings.memrise_auth_disabled:
        return await call_next(request)
    expected = settings.memrise_api_key
    if not expected:  # fail closed: no key configured
        return _unauthorized(request, "server authentication is not configured")
    provided = _api_key_from_request(request)
    if provided is not None and compare_digest(provided, expected):
        return await call_next(request)
    return _unauthorized(request, "invalid API key")


def _unauthorized(request: Request, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={
            "error": {
                "code": "unauthorized",
                "message": message,
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


def _api_key_from_request(request: Request) -> str | None:
    authorization = request.headers.get("authorization")
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            return token.strip()
    return request.headers.get("x-api-key")
