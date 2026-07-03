from typing import Protocol

from memrise.graph.schema import GraphSchemaPack


class GraphSchemaRegistry(Protocol):
    async def ensure_seeded(self) -> None: ...

    async def list_active_packs(
        self,
        *,
        namespace_id: str,
        project_id: str | None = None,
    ) -> list[GraphSchemaPack]: ...

    async def get_pack(self, pack_id: str) -> GraphSchemaPack | None: ...

    async def record_schema_candidate(
        self,
        *,
        namespace_id: str,
        domain: str,
        candidate_type: str,
        candidate_kind: str,
        fallback_type: str,
        example: dict[str, object],
    ) -> None: ...
