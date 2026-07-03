from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from memrise.runtime.settings import MemorySettings
from memrise.schemas.responses import MemoryExplanation, MemorySummary
from memrise_api.main import create_app
from memrise_api.settings import ApiSettings


class ApiMemoryStub:
    async def list_memories(
        self,
        *,
        namespace_id: str,
        agent_id: str,
        user_id: str | None = None,
        project_id: str | None = None,
    ) -> list[MemorySummary]:
        del namespace_id, agent_id, user_id, project_id
        return []

    async def explain(self, memory_id: str) -> MemoryExplanation:
        return MemoryExplanation(
            memory_id=memory_id,
            current_version=None,
            versions=[],
            provenance_episode_ids=[],
            graph_edges=[],
            retrieval_feedback=[],
        )


def _bootstrap_app_state(application) -> None:  # type: ignore[no-untyped-def]
    application.state.api_settings = ApiSettings()
    application.state.engine_settings = MemorySettings.model_construct(database_url=None)
    application.state.memory = ApiMemoryStub()


@pytest.fixture
def api_key() -> str:
    return "test-api-key"


@pytest.fixture
def app(api_key: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEMRISE_API_KEY", api_key)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    application = create_app()
    _bootstrap_app_state(application)
    return application


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client


@pytest.fixture
def mock_memory(app) -> ApiMemoryStub:
    return app.state.memory


@pytest.fixture
def auth_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}
