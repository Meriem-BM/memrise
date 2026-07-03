from dataclasses import dataclass, field, replace
from datetime import datetime

from memrise.core.enums import GraphClaimStatus
from memrise.core.graph import GraphClaim, GraphEntity
from memrise.core.time import utc_now
from memrise.graph.types import normalize_entity_name
from memrise.integrations.postgres.store.graph_claims import merge_aliases


@dataclass
class GraphClaimStoreStub:
    entities: dict[str, GraphEntity] = field(default_factory=dict)
    entities_by_identity: dict[tuple[str, str, str], str] = field(default_factory=dict)
    claims: dict[str, GraphClaim] = field(default_factory=dict)
    superseded_counts: list[tuple[str, str]] = field(default_factory=list)
    ambiguous_mentions: list[dict[str, object]] = field(default_factory=list)

    async def upsert_entity(
        self,
        *,
        entity_id: str,
        namespace_id: str,
        core_type: str,
        canonical_name: str,
        normalized_name: str,
        aliases: tuple[str, ...] = (),
        domain_type: str | None = None,
        stable_source_id: str | None = None,
        user_id: str | None = None,
        project_id: str | None = None,
    ) -> GraphEntity:
        now = utc_now()
        identity = (namespace_id, core_type, normalized_name)
        existing_id = self.entities_by_identity.get(identity)
        if existing_id is not None:
            existing = self.entities[existing_id]
            merged = replace(
                existing,
                canonical_name=canonical_name,
                aliases=tuple(merge_aliases(list(existing.aliases), aliases)),
                domain_type=domain_type if domain_type is not None else existing.domain_type,
                stable_source_id=(
                    stable_source_id if stable_source_id is not None else existing.stable_source_id
                ),
                user_id=user_id if user_id is not None else existing.user_id,
                project_id=project_id if project_id is not None else existing.project_id,
            )
            self.entities[existing_id] = merged
            return merged
        entity = GraphEntity(
            id=entity_id,
            namespace_id=namespace_id,
            core_type=core_type,
            domain_type=domain_type,
            canonical_name=canonical_name,
            normalized_name=normalized_name,
            aliases=aliases,
            stable_source_id=stable_source_id,
            user_id=user_id,
            project_id=project_id,
            created_at=now,
        )
        self.entities[entity_id] = entity
        self.entities_by_identity[identity] = entity_id
        return entity

    async def get_entity_by_identity(
        self,
        *,
        namespace_id: str,
        core_type: str,
        normalized_name: str,
    ) -> GraphEntity | None:
        entity_id = self.entities_by_identity.get((namespace_id, core_type, normalized_name))
        if entity_id is None:
            return None
        return self.entities.get(entity_id)

    async def get_entity_by_id(self, entity_id: str) -> GraphEntity | None:
        return self.entities.get(entity_id)

    async def get_entity_by_stable_source_id(
        self,
        *,
        namespace_id: str,
        stable_source_id: str,
    ) -> GraphEntity | None:
        for entity in self.entities.values():
            if entity.namespace_id == namespace_id and entity.stable_source_id == stable_source_id:
                return entity
        return None

    async def find_entities_by_term(
        self,
        *,
        namespace_id: str,
        term: str,
        core_type: str | None = None,
        user_id: str | None = None,
        project_id: str | None = None,
        limit: int = 5,
    ) -> list[GraphEntity]:
        del user_id, project_id
        stripped = term.strip()
        normalized = normalize_entity_name(stripped)
        folded = stripped.casefold()
        matches = []
        for entity in self.entities.values():
            if entity.namespace_id != namespace_id:
                continue
            if core_type is not None and entity.core_type != core_type:
                continue
            if entity.normalized_name == normalized or folded in entity.canonical_name.casefold():
                matches.append(entity)
                continue
            if any(
                normalize_entity_name(alias) == normalized or folded in alias.casefold()
                for alias in entity.aliases
            ):
                matches.append(entity)
            if len(matches) >= limit:
                break
        return matches

    async def insert_claim_if_absent(
        self,
        *,
        claim_id: str,
        namespace_id: str,
        subject_entity_id: str,
        predicate: str,
        object_entity_id: str,
        supporting_memory_version_id: str,
        evidence_text: str | None,
        confidence: float,
        valid_from: datetime,
        schema_version: str,
        extractor_version: str | None,
        extracted_at: datetime,
    ) -> GraphClaim:
        for claim in self.claims.values():
            if (
                claim.subject_entity_id == subject_entity_id
                and claim.predicate == predicate
                and claim.object_entity_id == object_entity_id
                and claim.supporting_memory_version_id == supporting_memory_version_id
            ):
                return claim
        claim = GraphClaim(
            id=claim_id,
            namespace_id=namespace_id,
            subject_entity_id=subject_entity_id,
            predicate=predicate,
            object_entity_id=object_entity_id,
            supporting_memory_version_id=supporting_memory_version_id,
            evidence_text=evidence_text,
            confidence=confidence,
            usefulness_score=0.5,
            status=GraphClaimStatus.ACTIVE,
            valid_from=valid_from,
            valid_until=None,
            superseded_by_claim_id=None,
            schema_version=schema_version,
            extractor_version=extractor_version,
            extracted_at=extracted_at,
        )
        self.claims[claim_id] = claim
        return claim

    async def supersede_claims_for_memory_version(
        self,
        *,
        namespace_id: str,
        memory_version_id: str,
        valid_until: datetime,
        superseded_by_claim_ids: dict[str, str] | None = None,
    ) -> int:
        del valid_until
        self.superseded_counts.append((namespace_id, memory_version_id))
        count = 0
        for claim in self.claims.values():
            if (
                claim.namespace_id == namespace_id
                and claim.supporting_memory_version_id == memory_version_id
                and claim.status == GraphClaimStatus.ACTIVE
            ):
                replacement = None
                if superseded_by_claim_ids is not None:
                    replacement = superseded_by_claim_ids.get(claim.id)
                self.claims[claim.id] = replace(
                    claim,
                    status=GraphClaimStatus.SUPERSEDED,
                    superseded_by_claim_id=replacement,
                )
                count += 1
        return count

    async def mark_claims_contradicted(
        self,
        *,
        namespace_id: str,
        claim_ids: list[str],
    ) -> int:
        count = 0
        for claim_id in claim_ids:
            claim = self.claims.get(claim_id)
            if claim is None or claim.namespace_id != namespace_id:
                continue
            self.claims[claim_id] = replace(claim, status=GraphClaimStatus.CONTRADICTED)
            count += 1
        return count

    async def record_ambiguous_mention(
        self,
        *,
        namespace_id: str,
        name: str,
        core_type: str,
        memory_version_id: str,
        candidate_entity_ids: tuple[str, ...],
    ) -> None:
        self.ambiguous_mentions.append(
            {
                "namespace_id": namespace_id,
                "name": name,
                "core_type": core_type,
                "memory_version_id": memory_version_id,
                "candidate_entity_ids": list(candidate_entity_ids),
            }
        )

    async def merge_entities(
        self,
        *,
        namespace_id: str,
        source_entity_id: str,
        target_entity_id: str,
    ) -> int:
        source = self.entities.get(source_entity_id)
        target = self.entities.get(target_entity_id)
        if source is None or target is None or source_entity_id == target_entity_id:
            return 0
        if source.namespace_id != namespace_id or target.namespace_id != namespace_id:
            return 0
        moved = 0
        for claim_id, claim in list(self.claims.items()):
            changes = {}
            if claim.subject_entity_id == source_entity_id:
                changes["subject_entity_id"] = target_entity_id
            if claim.object_entity_id == source_entity_id:
                changes["object_entity_id"] = target_entity_id
            if changes:
                self.claims[claim_id] = replace(claim, **changes)
                moved += len(changes)
        merged_aliases = tuple(
            merge_aliases(list(target.aliases), (source.canonical_name, *source.aliases))
        )
        updated = replace(
            target,
            aliases=merged_aliases,
            stable_source_id=target.stable_source_id or source.stable_source_id,
        )
        self.entities[target_entity_id] = updated
        del self.entities[source_entity_id]
        self.entities_by_identity.pop(
            (source.namespace_id, source.core_type, source.normalized_name), None
        )
        return moved

    async def update_claim_usefulness(self, *, claim_id: str, usefulness_score: float) -> None:
        claim = self.claims.get(claim_id)
        if claim is None:
            return
        self.claims[claim_id] = replace(claim, usefulness_score=usefulness_score)

    async def expire_due_claims(self, *, now: datetime) -> int:
        expired = 0
        for claim_id, claim in list(self.claims.items()):
            if (
                claim.status == GraphClaimStatus.ACTIVE
                and claim.valid_until is not None
                and claim.valid_until <= now
            ):
                self.claims[claim_id] = replace(claim, status=GraphClaimStatus.EXPIRED)
                expired += 1
        return expired

    async def list_conflicting_active_claims(
        self,
        *,
        namespace_id: str,
        subject_entity_id: str,
        predicate: str,
        object_entity_id: str,
        excluding_memory_version_id: str,
    ) -> list[GraphClaim]:
        return [
            claim
            for claim in self.claims.values()
            if claim.namespace_id == namespace_id
            and claim.subject_entity_id == subject_entity_id
            and claim.predicate == predicate
            and claim.object_entity_id == object_entity_id
            and claim.supporting_memory_version_id != excluding_memory_version_id
            and claim.status == GraphClaimStatus.ACTIVE
        ]

    async def list_active_claims(
        self,
        *,
        namespace_id: str,
        memory_version_id: str | None = None,
    ) -> list[GraphClaim]:
        claims = [
            claim
            for claim in self.claims.values()
            if claim.namespace_id == namespace_id and claim.status == GraphClaimStatus.ACTIVE
        ]
        if memory_version_id is not None:
            claims = [
                claim for claim in claims if claim.supporting_memory_version_id == memory_version_id
            ]
        return claims
