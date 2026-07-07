import httpx
from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    PermissionDeniedError,
    RateLimitError,
)

from memrise.integrations.qwen.errors import QwenProviderError
from memrise.integrations.qwen.providers import _provider_error

_REQ = httpx.Request("POST", "https://dashscope/api")


def _resp(status: int) -> httpx.Response:
    return httpx.Response(status, request=_REQ)


def test_quota_error_maps_to_billing_message() -> None:
    err = PermissionDeniedError("free quota exhausted", response=_resp(403), body=None)
    mapped = _provider_error(err, "extraction")
    assert isinstance(mapped, QwenProviderError)
    assert "quota" in str(mapped).lower()
    assert "billing" in str(mapped).lower()


def test_rate_limit_maps_to_retry_message() -> None:
    err = RateLimitError("slow down", response=_resp(429), body=None)
    assert "rate limit" in str(_provider_error(err, "answer")).lower()


def test_auth_error_keeps_auth_message() -> None:
    err = AuthenticationError("bad key", response=_resp(401), body=None)
    assert "authentication failed" in str(_provider_error(err, "embedding")).lower()


def test_other_status_reports_code() -> None:
    err = APIStatusError("boom", response=_resp(500), body=None)
    assert "500" in str(_provider_error(err, "consolidation"))


def test_connection_error_is_unavailable() -> None:
    err = APIConnectionError(request=_REQ)
    assert "unavailable" in str(_provider_error(err, "extraction")).lower()
