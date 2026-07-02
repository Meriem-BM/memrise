import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_missing_api_key_returns_unauthorized(client: AsyncClient) -> None:
    response = await client.get("/v1/memories", params={"namespace_id": "ns", "agent_id": "agent"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_invalid_api_key_returns_unauthorized(client: AsyncClient) -> None:
    response = await client.get(
        "/v1/memories",
        params={"namespace_id": "ns", "agent_id": "agent"},
        headers={"Authorization": "Bearer wrong-key"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_valid_api_key_allows_access(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.get(
        "/v1/memories",
        params={"namespace_id": "ns", "agent_id": "agent"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == []
