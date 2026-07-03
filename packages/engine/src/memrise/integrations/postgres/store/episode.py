from copy import deepcopy

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from memrise.core.errors import IdempotencyConflictError
from memrise.core.models import Episode, EpisodeSaveOutcome
from memrise.integrations.postgres.schema.mappers import episode_from_row
from memrise.integrations.postgres.schema.models import EpisodeRow
from memrise.integrations.postgres.session import session_scope


def episode_payload_matches(existing: Episode, incoming: Episode) -> bool:
    return (
        existing.kind == incoming.kind
        and existing.content == incoming.content
        and existing.agent_id == incoming.agent_id
        and existing.session_id == incoming.session_id
        and existing.user_id == incoming.user_id
        and existing.project_id == incoming.project_id
        and existing.metadata == incoming.metadata
    )


def episode_insert_mapping(episode: Episode) -> dict[str, object]:
    return {
        "id": episode.id,
        "namespace_id": episode.namespace_id,
        "agent_id": episode.agent_id,
        "user_id": episode.user_id,
        "session_id": episode.session_id,
        "project_id": episode.project_id,
        "kind": episode.kind.value,
        "content": episode.content,
        "metadata_": deepcopy(episode.metadata),
        "idempotency_key": episode.idempotency_key,
        "created_at": episode.created_at,
    }


class PostgresEpisodeRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save_episode(self, episode: Episode) -> EpisodeSaveOutcome:
        async with session_scope(self._session_factory) as session:
            if episode.idempotency_key is not None:
                inserted_id = await session.scalar(
                    insert(EpisodeRow)
                    .values(episode_insert_mapping(episode))
                    .on_conflict_do_nothing(
                        index_elements=["namespace_id", "idempotency_key"],
                        index_where=text("idempotency_key IS NOT NULL"),
                    )
                    .returning(EpisodeRow.id)
                )
                if inserted_id is not None:
                    return EpisodeSaveOutcome(episode=episode, created=True)
                existing = await session.scalar(
                    select(EpisodeRow).where(
                        EpisodeRow.namespace_id == episode.namespace_id,
                        EpisodeRow.idempotency_key == episode.idempotency_key,
                    )
                )
                if existing is None:
                    msg = (
                        "episode idempotency conflict could not be resolved for key "
                        f"{episode.idempotency_key!r}"
                    )
                    raise RuntimeError(msg)
                stored = episode_from_row(existing)
                if not episode_payload_matches(stored, episode):
                    msg = (
                        "idempotency key already used with a different capture payload: "
                        f"{episode.idempotency_key!r}"
                    )
                    raise IdempotencyConflictError(msg)
                return EpisodeSaveOutcome(episode=stored, created=False)

            existing = await session.get(EpisodeRow, episode.id)
            if existing is not None:
                return EpisodeSaveOutcome(episode=episode_from_row(existing), created=False)
            session.add(
                EpisodeRow(
                    id=episode.id,
                    namespace_id=episode.namespace_id,
                    agent_id=episode.agent_id,
                    user_id=episode.user_id,
                    session_id=episode.session_id,
                    project_id=episode.project_id,
                    kind=episode.kind.value,
                    content=episode.content,
                    metadata_=deepcopy(episode.metadata),
                    idempotency_key=episode.idempotency_key,
                    created_at=episode.created_at,
                )
            )
            return EpisodeSaveOutcome(episode=episode, created=True)

    async def get_episode(self, episode_id: str) -> Episode | None:
        async with self._session_factory() as session:
            row = await session.get(EpisodeRow, episode_id)
            return episode_from_row(row) if row else None

    async def list_session_episodes(
        self,
        *,
        namespace_id: str,
        agent_id: str,
        session_id: str,
    ) -> list[Episode]:
        async with self._session_factory() as session:
            rows = (
                await session.scalars(
                    select(EpisodeRow).where(
                        EpisodeRow.namespace_id == namespace_id,
                        EpisodeRow.agent_id == agent_id,
                        EpisodeRow.session_id == session_id,
                    )
                )
            ).all()
            return [episode_from_row(row) for row in rows]
