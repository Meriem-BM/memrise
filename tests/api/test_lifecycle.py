import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_run_lifecycle(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.post("/v1/lifecycle/run", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["expired_memory_versions"] == 0
    assert set(body) == {
        "expired_memory_versions",
        "decayed_versions",
        "resolved_contested",
        "expired_claims",
        "expired_edges",
    }


@pytest.mark.asyncio
async def test_list_memories_accepts_status_filter(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.get(
        "/v1/memories",
        params={"namespace_id": "ns", "agent_id": "agent", "status": "contested"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_memories_rejects_unknown_status(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.get(
        "/v1/memories",
        params={"namespace_id": "ns", "agent_id": "agent", "status": "bogus"},
        headers=auth_headers,
    )

    assert response.status_code == 422
