from datetime import datetime
from typing import Protocol

from memrise.core.graph import GraphClaim, GraphEntity


class GraphClaimStore(Protocol):
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
    ) -> GraphEntity: ...

    async def get_entity_by_identity(
        self,
        *,
        namespace_id: str,
        core_type: str,
        normalized_name: str,
    ) -> GraphEntity | None: ...

    async def get_entity_by_id(self, entity_id: str) -> GraphEntity | None: ...

    async def get_entity_by_stable_source_id(
        self,
        *,
        namespace_id: str,
        stable_source_id: str,
    ) -> GraphEntity | None: ...

    async def find_entities_by_term(
        self,
        *,
        namespace_id: str,
        term: str,
        core_type: str | None = None,
        user_id: str | None = None,
        project_id: str | None = None,
        limit: int = 5,
    ) -> list[GraphEntity]: ...

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
    ) -> GraphClaim: ...

    async def supersede_claims_for_memory_version(
        self,
        *,
        namespace_id: str,
        memory_version_id: str,
        valid_until: datetime,
        superseded_by_claim_ids: dict[str, str] | None = None,
    ) -> int: ...

    async def mark_claims_contradicted(
        self,
        *,
        namespace_id: str,
        claim_ids: list[str],
    ) -> int: ...

    async def list_active_claims(
        self,
        *,
        namespace_id: str,
        memory_version_id: str | None = None,
    ) -> list[GraphClaim]: ...

    async def update_claim_usefulness(self, *, claim_id: str, usefulness_score: float) -> None: ...

    async def record_ambiguous_mention(
        self,
        *,
        namespace_id: str,
        name: str,
        core_type: str,
        memory_version_id: str,
        candidate_entity_ids: tuple[str, ...],
    ) -> None: ...

    async def merge_entities(
        self,
        *,
        namespace_id: str,
        source_entity_id: str,
        target_entity_id: str,
    ) -> int:
        """Re-point claims onto target, union aliases, drop source; returns moved claims."""
        ...

    async def expire_due_claims(self, *, now: datetime) -> int: ...

    async def list_active_claims_by_subject_predicate(
        self,
        *,
        namespace_id: str,
        subject_entity_id: str,
        predicate: str,
    ) -> list[GraphClaim]: ...

    async def supersede_claims_by_ids(
        self,
        *,
        namespace_id: str,
        claim_ids: list[str],
        valid_until: datetime,
        superseded_by_claim_id: str,
    ) -> int: ...

    async def list_conflicting_active_claims(
        self,
        *,
        namespace_id: str,
        subject_entity_id: str,
        predicate: str,
        object_entity_id: str,
        excluding_memory_version_id: str,
    ) -> list[GraphClaim]: ...
