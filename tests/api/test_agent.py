import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_agent_respond(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.post(
        "/v1/agent/respond",
        json={"namespace_id": "ns", "agent_id": "agent", "query": "what is my name?"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["answer"] == "mock answer for what is my name?"
    assert body["model_name"] == "mock-qwen"
    assert body["memory_enabled"] is True
    assert body["retrieval"]["retrieval_id"] == "retrieval-1"


@pytest.mark.asyncio
async def test_agent_respond_can_skip_memory(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/v1/agent/respond",
        json={
            "namespace_id": "ns",
            "agent_id": "agent",
            "query": "what is my name?",
            "use_memory": False,
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["answer"] == "mock answer for what is my name?"
    assert body["memory_enabled"] is False
    assert body["retrieval"] is None


@pytest.mark.asyncio
async def test_agent_respond_requires_query(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/v1/agent/respond",
        json={"namespace_id": "ns", "agent_id": "agent"},
        headers=auth_headers,
    )

    assert response.status_code == 422
