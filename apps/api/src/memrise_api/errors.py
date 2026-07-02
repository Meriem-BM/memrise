from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ApiError(Exception):
    code: str
    message: str
    status_code: int


class NotFoundError(ApiError):
    def __init__(self, message: str) -> None:
        super().__init__(code="not_found", message=message, status_code=404)


class DependencyUnavailableError(ApiError):
    def __init__(self, message: str) -> None:
        super().__init__(code="dependency_unavailable", message=message, status_code=503)
