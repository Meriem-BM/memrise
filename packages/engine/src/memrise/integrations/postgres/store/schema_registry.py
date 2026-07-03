from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from memrise.core.time import utc_now
from memrise.graph.schema import (
    CORE_PACK_DEFINITION,
    SOFTWARE_PACK_DEFINITION,
    GraphSchemaPack,
    pack_from_definition,
)
from memrise.integrations.postgres.schema.models import GraphSchemaCandidateRow, GraphSchemaPackRow
from memrise.integrations.postgres.session import session_scope
from memrise.ports.ids import IdGenerator


def _pack_from_row(row: GraphSchemaPackRow) -> GraphSchemaPack:
    return pack_from_definition(
        pack_id=row.id,
        namespace_id=row.namespace_id,
        project_id=row.project_id,
        status=row.status,
        definition=row.definition,
    )


class PostgresGraphSchemaRegistry:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        id_generator: IdGenerator,
    ) -> None:
        self._session_factory = session_factory
        self._ids = id_generator

    async def ensure_seeded(self) -> None:
        now = utc_now()
        seeds = (
            ("schema-core-1.0", CORE_PACK_DEFINITION),
            ("schema-software-1.0", SOFTWARE_PACK_DEFINITION),
        )
        async with session_scope(self._session_factory) as session:
            for pack_id, definition in seeds:
                await session.execute(
                    insert(GraphSchemaPackRow)
                    .values(
                        id=pack_id,
                        namespace_id=None,
                        project_id=None,
                        domain=str(definition["domain"]),
                        version=str(definition["version"]),
                        status="active",
                        definition=definition,
                        created_at=now,
                        updated_at=now,
                    )
                    .on_conflict_do_nothing(
                        index_elements=["namespace_id", "project_id", "domain", "version"]
                    )
                )

    async def list_active_packs(
        self,
        *,
        namespace_id: str,
        project_id: str | None = None,
    ) -> list[GraphSchemaPack]:
        await self.ensure_seeded()
        async with self._session_factory() as session:
            global_rows = (
                await session.scalars(
                    select(GraphSchemaPackRow).where(
                        GraphSchemaPackRow.status == "active",
                        GraphSchemaPackRow.namespace_id.is_(None),
                    )
                )
            ).all()
            scoped_rows = (
                await session.scalars(
                    select(GraphSchemaPackRow).where(
                        GraphSchemaPackRow.status == "active",
                        GraphSchemaPackRow.namespace_id == namespace_id,
                    )
                )
            ).all()
        packs = [_pack_from_row(row) for row in global_rows]
        if project_id is not None:
            packs.extend(
                pack
                for pack in (_pack_from_row(row) for row in scoped_rows)
                if pack.project_id in {None, project_id}
            )
        else:
            packs.extend(_pack_from_row(row) for row in scoped_rows)
        deduped: dict[str, GraphSchemaPack] = {}
        for pack in packs:
            deduped[pack.id] = pack
        return list(deduped.values())

    async def get_pack(self, pack_id: str) -> GraphSchemaPack | None:
        async with self._session_factory() as session:
            row = (
                await session.scalars(
                    select(GraphSchemaPackRow).where(GraphSchemaPackRow.id == pack_id)
                )
            ).first()
            if row is None:
                return None
            return _pack_from_row(row)

    async def record_schema_candidate(
        self,
        *,
        namespace_id: str,
        domain: str,
        candidate_type: str,
        candidate_kind: str,
        fallback_type: str,
        example: dict[str, object],
    ) -> None:
        now = utc_now()
        candidate_id = self._ids.new_id("schem")
        async with session_scope(self._session_factory) as session:
            existing = (
                await session.scalars(
                    select(GraphSchemaCandidateRow).where(
                        GraphSchemaCandidateRow.namespace_id == namespace_id,
                        GraphSchemaCandidateRow.domain == domain,
                        GraphSchemaCandidateRow.candidate_type == candidate_type,
                        GraphSchemaCandidateRow.candidate_kind == candidate_kind,
                    )
                )
            ).first()
            if existing is not None:
                examples = list(existing.example_context or [])
                examples.append(example)
                existing.example_context = examples[-5:]
                existing.occurrence_count = existing.occurrence_count + 1
                existing.updated_at = now
                return
            session.add(
                GraphSchemaCandidateRow(
                    id=candidate_id,
                    namespace_id=namespace_id,
                    domain=domain,
                    candidate_type=candidate_type,
                    candidate_kind=candidate_kind,
                    fallback_type=fallback_type,
                    occurrence_count=1,
                    example_context=[example],
                    status="proposed",
                    created_at=now,
                    updated_at=now,
                )
            )
