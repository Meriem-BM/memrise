import hashlib
from datetime import UTC, datetime

from memrise.core.enums import Criticality, MemoryOperation, MemoryType
from memrise.ports.providers import (
    EmbeddingProvider,
    ExtractedGraphRelation,
    ExtractedMemoryCandidate,
    ExtractionResult,
)


class DeterministicEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimensions: int = 1024) -> None:
        self._dimensions = dimensions

    async def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        for index in range(self._dimensions):
            byte = digest[index % len(digest)]
            values.append((byte / 255.0) - 0.5)
        return values


class DeterministicCompletionProvider:
    async def extract_memories(self, *, text: str, context: dict[str, object]) -> ExtractionResult:
        lowered = text.lower()
        candidates: list[ExtractedMemoryCandidate] = []
        project_id = str(context.get("project_id") or "global")
        subject = "Atlas" if "atla" in lowered or project_id.lower() == "atlas" else project_id

        if "pnpm" in lowered:
            structured = {"tool": "pnpm", "replaces": "npm" if "npm" in lowered else None}
            candidates.append(
                ExtractedMemoryCandidate(
                    type=MemoryType.DECISION,
                    subject=subject,
                    key="package_manager",
                    content=f"{subject} uses pnpm for dependency installation.",
                    structured_value=structured,
                    confidence=0.96,
                    importance=0.86,
                    criticality=Criticality.HIGH_PRIORITY,
                    operation_hint=MemoryOperation.SUPERSEDE
                    if "npm" in lowered
                    else MemoryOperation.ADD,
                    graph_relations=[
                        ExtractedGraphRelation(source=subject, relation="USES", target="pnpm"),
                        ExtractedGraphRelation(source="pnpm", relation="REPLACED", target="npm"),
                    ],
                )
            )
        elif "npm" in lowered:
            candidates.append(
                ExtractedMemoryCandidate(
                    type=MemoryType.DECISION,
                    subject=subject,
                    key="package_manager",
                    content=f"{subject} uses npm for dependency installation.",
                    structured_value={"tool": "npm"},
                    confidence=0.9,
                    importance=0.75,
                    criticality=Criticality.HIGH_PRIORITY,
                    operation_hint=MemoryOperation.ADD,
                    graph_relations=[
                        ExtractedGraphRelation(source=subject, relation="USES", target="npm")
                    ],
                )
            )

        if "never" in lowered and "lockfile" in lowered:
            candidates.append(
                ExtractedMemoryCandidate(
                    type=MemoryType.CONSTRAINT,
                    subject=subject,
                    key="generated_lockfile_manual_edits",
                    content=f"Never edit {subject}'s generated lockfile manually.",
                    structured_value={"forbidden_action": "manual_lockfile_edit"},
                    confidence=0.98,
                    importance=0.95,
                    criticality=Criticality.MUST_INCLUDE,
                    operation_hint=MemoryOperation.ADD,
                    graph_relations=[
                        ExtractedGraphRelation(
                            source=subject, relation="HAS_CONSTRAINT", target="lockfile"
                        )
                    ],
                )
            )

        if "temporary" in lowered or "until" in lowered:
            candidates.append(
                ExtractedMemoryCandidate(
                    type=MemoryType.FACT,
                    subject=subject,
                    key="temporary_note",
                    content=text,
                    structured_value={"temporary": True},
                    confidence=0.6,
                    importance=0.4,
                    criticality=Criticality.NORMAL,
                    operation_hint=MemoryOperation.ADD,
                    valid_until=datetime.now(UTC).isoformat(),
                )
            )

        return ExtractionResult(
            candidates=candidates,
            model_name="deterministic-test-provider",
            prompt_version="deterministic-v1",
        )
