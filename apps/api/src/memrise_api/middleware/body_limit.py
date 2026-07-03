from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import JSONResponse, Response


async def body_limit_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        max_bytes = request.app.state.api_settings.memrise_request_max_bytes
        try:
            declared = int(content_length)
        except ValueError:
            declared = None
        if declared is not None and declared > max_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "code": "payload_too_large",
                        "message": f"request body exceeds {max_bytes} bytes",
                        "request_id": getattr(request.state, "request_id", None),
                    }
                },
            )
    return await call_next(request)
