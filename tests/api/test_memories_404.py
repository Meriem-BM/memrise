import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_memory_returns_404_when_missing(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.get("/v1/memories/mem_missing", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_explain_memory_returns_404_when_missing(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.get("/v1/memories/mem_missing/explanation", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
