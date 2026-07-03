from collections.abc import Awaitable, Callable

from fastapi.exceptions import RequestValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from memrise.core.errors import IdempotencyConflictError
from memrise.integrations.qwen.errors import QwenProviderError
from memrise_api.errors import ApiError, ConflictError, DependencyUnavailableError


async def error_handler_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    try:
        return await call_next(request)
    except ApiError as exc:
        return _error_response(request, exc.status_code, exc.code, exc.message)
    except IdempotencyConflictError as exc:
        conflict = ConflictError(str(exc))
        return _error_response(
            request,
            conflict.status_code,
            conflict.code,
            conflict.message,
        )
    except QwenProviderError as exc:
        unavailable = DependencyUnavailableError(str(exc))
        return _error_response(
            request,
            unavailable.status_code,
            unavailable.code,
            unavailable.message,
        )
    except RequestValidationError as exc:
        return _error_response(request, 422, "validation_error", str(exc))
    except Exception:
        return _error_response(request, 500, "internal_error", "internal server error")


def _error_response(request: Request, status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )
