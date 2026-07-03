from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from memrise.core.enums import GraphEdgeStatus
from memrise.core.graph import (
    GraphEdge,
    GraphPath,
    GraphProjection,
    GraphProjectionResult,
    GraphSearchRequest,
    clamp_graph_depth,
)
from memrise.core.time import utc_now
from memrise.graph.identity import node_identity_key
from memrise.graph.types import coerce_node_label, coerce_relation, normalize_entity_name
from memrise.integrations.apache_age import statements as stmt
from memrise.integrations.apache_age.cypher import CypherExecutor
from memrise.integrations.apache_age.errors import AgeUnavailableError
from memrise.integrations.apache_age.row_parser import (
    build_path,
    edge_claim_id,
    parse_edge,
    parse_vertex,
)
from memrise.ports.ids import IdGenerator


class AgeGraphRepository:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        id_generator: IdGenerator,
        graph_name: str = stmt.GRAPH_NAME,
        query_timeout_seconds: float = 2.0,
    ) -> None:
        self._session_factory = session_factory
        self._graph_name = graph_name
        self._ids = id_generator
        self._available: bool | None = None
        self._cypher = CypherExecutor(
            session_factory,
            graph_name=graph_name,
            query_timeout_ms=int(query_timeout_seconds * 1000),
        )

    async def is_available(self) -> bool:
        if self._available is None:
            async with self._session_factory() as session:
                installed = await session.scalar(
                    text("select exists (select 1 from pg_extension where extname = 'age')")
                )
            self._available = bool(installed)
        return self._available

    async def project(self, projection: GraphProjection) -> GraphProjectionResult:
        if not await self.is_available():
            msg = "apache age extension is not installed"
            raise AgeUnavailableError(msg)

        superseded_count = 0
        if projection.supersedes_version_id is not None:
            superseded_count = await self._supersede_edges_for_version(
                namespace_id=projection.namespace_id,
                memory_version_id=projection.supersedes_version_id,
                valid_until=projection.valid_from,
            )

        node_uid_by_temp_id: dict[str, str] = {}
        created_node_uids: list[str] = []
        created_edge_uids: list[str] = []

        for candidate in projection.nodes:
            uid = self.stable_node_uid(
                namespace_id=projection.namespace_id,
                node_type=candidate.node_type,
                name=candidate.name,
            )
            node_uid_by_temp_id[candidate.temporary_id] = uid
            await self._upsert_node(
                uid=uid,
                namespace_id=projection.namespace_id,
                node_type=candidate.node_type,
                canonical_name=candidate.name,
                normalized_name=normalize_entity_name(candidate.name),
                aliases=[candidate.name],
                created_at=projection.valid_from,
            )
            created_node_uids.append(uid)

        for edge in projection.edges:
            source_uid = node_uid_by_temp_id.get(edge.source)
            target_uid = node_uid_by_temp_id.get(edge.target)
            if source_uid is None or target_uid is None:
                continue
            source_type = coerce_node_label(
                next(
                    (
                        node.node_type
                        for node in projection.nodes
                        if node.temporary_id == edge.source
                    ),
                    None,
                )
            )
            target_type = coerce_node_label(
                next(
                    (
                        node.node_type
                        for node in projection.nodes
                        if node.temporary_id == edge.target
                    ),
                    None,
                )
            )
            edge_uid = self._edge_uid(
                memory_version_id=projection.memory_version_id,
                source_uid=source_uid,
                relation=edge.relation,
                target_uid=target_uid,
            )
            if await self._edge_exists(edge_uid=edge_uid):
                created_edge_uids.append(edge_uid)
                continue
            await self._create_edge(
                edge_uid=edge_uid,
                namespace_id=projection.namespace_id,
                source_uid=source_uid,
                target_uid=target_uid,
                source_type=source_type,
                target_type=target_type,
                relation=coerce_relation(edge.relation),
                source_memory_version_id=projection.memory_version_id,
                claim_id=edge.claim_id,
                confidence=projection.confidence,
                usefulness_score=edge.usefulness_score,
                valid_from=projection.valid_from,
            )
            created_edge_uids.append(edge_uid)

        return GraphProjectionResult(
            memory_version_id=projection.memory_version_id,
            node_uids=tuple(created_node_uids),
            edge_uids=tuple(created_edge_uids),
            superseded_edge_count=superseded_count,
        )

    async def search(self, request: GraphSearchRequest) -> list[GraphPath]:
        if not await self.is_available():
            return []
        if request.exact_match:
            normalized = normalize_entity_name(request.query)
            terms = [normalized] if normalized else []
        else:
            terms = [term for term in normalize_entity_name(request.query).split() if term]
        if not terms:
            return []
        depth = clamp_graph_depth(request.depth)
        paths: list[GraphPath] = []
        now_iso = utc_now().isoformat()
        for term in terms:
            if depth == 1:
                rows = await self._cypher.run(
                    stmt.one_hop_statement(exact_match=request.exact_match),
                    {
                        "namespace_id": request.namespace_id,
                        "term": term,
                        "now": now_iso,
                        "limit": request.max_paths,
                    },
                    columns=("seed", "r", "neighbor"),
                )
                for row in rows:
                    seed = parse_vertex(row["seed"])
                    edge = parse_edge(row["r"])
                    neighbor = parse_vertex(row["neighbor"])
                    if seed is None or edge is None or neighbor is None:
                        continue
                    built = build_path(
                        nodes=[node for node in [seed, neighbor] if node is not None],
                        edges=[edge],
                        seed_match_score=1.0,
                    )
                    if built is not None:
                        paths.append(built)
            else:
                rows = await self._cypher.run(
                    stmt.two_hop_statement(exact_match=request.exact_match),
                    {
                        "namespace_id": request.namespace_id,
                        "term": term,
                        "now": now_iso,
                        "limit": request.max_paths,
                    },
                    columns=("seed", "r1", "mid", "r2", "leaf"),
                )
                for row in rows:
                    seed = parse_vertex(row["seed"])
                    edge1 = parse_edge(row["r1"])
                    mid = parse_vertex(row["mid"])
                    edge2 = parse_edge(row["r2"])
                    leaf = parse_vertex(row["leaf"])
                    if None in {seed, edge1, mid, edge2, leaf}:
                        continue
                    built = build_path(
                        nodes=[node for node in [seed, mid, leaf] if node is not None],
                        edges=[edge for edge in [edge1, edge2] if edge is not None],
                        seed_match_score=0.8,
                    )
                    if built is not None:
                        paths.append(built)
            if len(paths) >= request.max_paths:
                break
        return paths[: request.max_paths]

    async def get_neighborhood(
        self,
        *,
        node_uid: str,
        namespace_id: str,
        depth: int,
    ) -> list[GraphPath]:
        del depth
        if not await self.is_available():
            return []
        rows = await self._cypher.run(
            stmt.NEIGHBORHOOD_BY_UID,
            {
                "node_uid": node_uid,
                "namespace_id": namespace_id,
                "now": utc_now().isoformat(),
                "limit": 20,
            },
            columns=("seed", "r", "neighbor"),
        )
        paths: list[GraphPath] = []
        for row in rows:
            seed = parse_vertex(row["seed"])
            edge = parse_edge(row["r"])
            neighbor = parse_vertex(row["neighbor"])
            if seed is None or edge is None or neighbor is None:
                continue
            built = build_path(
                nodes=[seed, neighbor],
                edges=[edge],
                seed_match_score=1.0,
            )
            if built is not None:
                paths.append(built)
        return paths

    async def update_edge_usefulness(self, edge_uid: str, usefulness_score: float) -> str | None:
        rows = await self._cypher.run(
            stmt.UPDATE_EDGE_USEFULNESS,
            {
                "edge_uid": edge_uid,
                "usefulness_score": usefulness_score,
            },
            columns=("r",),
        )
        if not rows:
            return None
        return edge_claim_id(rows[0].get("r"))

    async def expire_due_edges(self, *, now: datetime) -> int:
        if not await self.is_available():
            return 0
        rows = await self._cypher.run(
            stmt.EXPIRE_DUE_EDGES,
            {"now": now.isoformat()},
            columns=("expired_count",),
        )
        if not rows:
            return 0
        return int(str(rows[0].get("expired_count", 0) or 0))

    async def list_edges_for_memory_version(
        self,
        *,
        namespace_id: str,
        memory_version_id: str,
    ) -> list[GraphEdge]:
        if not await self.is_available():
            return []
        rows = await self._cypher.run(
            stmt.EDGES_FOR_MEMORY_VERSION,
            {
                "namespace_id": namespace_id,
                "memory_version_id": memory_version_id,
            },
            columns=("r",),
        )
        edges: list[GraphEdge] = []
        for row in rows:
            edge = parse_edge(row.get("r"))
            if edge is not None:
                edges.append(edge)
        return edges

    async def _upsert_node(
        self,
        *,
        uid: str,
        namespace_id: str,
        node_type: str,
        canonical_name: str,
        normalized_name: str,
        aliases: list[str],
        created_at: datetime,
    ) -> None:
        label = coerce_node_label(node_type)
        existing = await self._cypher.run(
            stmt.MATCH_NODE_BY_IDENTITY.format(label=stmt.node_label(label)),
            {
                "namespace_id": namespace_id,
                "type": label,
                "normalized_name": normalized_name,
            },
            columns=("n",),
        )
        if existing:
            await self._cypher.run(
                stmt.UPDATE_NODE_ALIASES.format(label=stmt.node_label(label)),
                {
                    "uid": uid,
                    "namespace_id": namespace_id,
                    "aliases": aliases,
                },
                columns=("n",),
            )
            return
        await self._cypher.run(
            stmt.CREATE_NODE.format(label=stmt.node_label(label)),
            {
                "uid": uid,
                "namespace_id": namespace_id,
                "type": label,
                "canonical_name": canonical_name,
                "normalized_name": normalized_name,
                "aliases": aliases,
                "created_at": created_at.isoformat(),
            },
            columns=("n",),
        )

    async def _create_edge(
        self,
        *,
        edge_uid: str,
        namespace_id: str,
        source_uid: str,
        target_uid: str,
        source_type: str,
        target_type: str,
        relation: str,
        source_memory_version_id: str,
        claim_id: str | None,
        confidence: float,
        usefulness_score: float,
        valid_from: datetime,
    ) -> None:
        await self._cypher.run(
            stmt.CREATE_EDGE.format(
                source_label=stmt.node_label(source_type),
                target_label=stmt.node_label(target_type),
                relation=stmt.relation_label(relation),
            ),
            {
                "edge_uid": edge_uid,
                "namespace_id": namespace_id,
                "source_uid": source_uid,
                "target_uid": target_uid,
                "relation_name": relation,
                "source_memory_version_id": source_memory_version_id,
                "claim_id": claim_id,
                "status": GraphEdgeStatus.ACTIVE.value,
                "confidence": confidence,
                "usefulness_score": usefulness_score,
                "valid_from": valid_from.isoformat(),
                "valid_until": None,
            },
            columns=("r",),
        )

    async def _edge_exists(self, *, edge_uid: str) -> bool:
        rows = await self._cypher.run(
            stmt.EDGE_EXISTS,
            {"edge_uid": edge_uid},
            columns=("r",),
        )
        return bool(rows)

    async def _supersede_edges_for_version(
        self,
        *,
        namespace_id: str,
        memory_version_id: str,
        valid_until: datetime,
    ) -> int:
        rows = await self._cypher.run(
            stmt.SUPERSEDE_EDGES_FOR_VERSION,
            {
                "namespace_id": namespace_id,
                "memory_version_id": memory_version_id,
                "valid_until": valid_until.isoformat(),
            },
            columns=("superseded_count",),
        )
        if not rows:
            return 0
        value = rows[0].get("superseded_count", 0)
        return int(str(value or 0))

    def stable_node_uid(
        self,
        *,
        namespace_id: str,
        node_type: str,
        name: str,
    ) -> str:
        return (
            f"node-{node_identity_key(namespace_id=namespace_id, node_type=node_type, name=name)}"
        )

    def _edge_uid(
        self,
        *,
        memory_version_id: str,
        source_uid: str,
        relation: str,
        target_uid: str,
    ) -> str:
        return f"edge-{memory_version_id}-{source_uid}-{relation}-{target_uid}"
