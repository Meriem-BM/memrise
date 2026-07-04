import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_session_episodes(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.get(
        "/v1/episodes",
        params={"namespace_id": "ns", "agent_id": "agent", "session_id": "session-1"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body == []


@pytest.mark.asyncio
async def test_list_episode_candidates(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.get("/v1/episodes/ep_1/candidates", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_session_episodes_requires_session_id(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.get(
        "/v1/episodes",
        params={"namespace_id": "ns", "agent_id": "agent"},
        headers=auth_headers,
    )

    assert response.status_code == 422
