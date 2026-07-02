from collections.abc import Awaitable, Callable
from uuid import uuid4

from starlette.requests import Request
from starlette.responses import Response


async def request_id_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get("x-request-id") or f"req_{uuid4().hex}"
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response
