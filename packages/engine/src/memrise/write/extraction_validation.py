from __future__ import annotations

import re
from dataclasses import dataclass

from memrise.core.enums import CandidateStageStatus, Criticality, MemoryOperation
from memrise.ports.providers import (
    EpisodeDurability,
    EvidenceRole,
    ExtractedMemoryCandidate,
    ExtractionResult,
    Sensitivity,
)

MIN_EXTRACTED_CONFIDENCE = 0.35
MIN_EXTRACTED_IMPORTANCE = 0.15
PROMOTION_SCORE_THRESHOLD = 0.58

_SECRET_PATTERNS = (
    re.compile(r"\b(?:api[_-]?key|secret|password|token)\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9]{16,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)


@dataclass(frozen=True, slots=True)
class CandidatePromotionDecision:
    candidate_index: int
    candidate: ExtractedMemoryCandidate | None
    status: CandidateStageStatus
    promotion_score: float
    rejection_reason: str | None = None

    @property
    def should_promote(self) -> bool:
        return self.status == CandidateStageStatus.STAGED and self.candidate is not None


class ExtractionValidationPolicy:
    """Deterministic guardrails for model-proposed memory candidates."""

    def decisions_for_episode(
        self,
        *,
        extraction: ExtractionResult,
        episode_content: str,
    ) -> list[CandidatePromotionDecision]:
        classification = extraction.classification
        if not classification.should_extract:
            return [_classification_rejection("classification:no_extract")]
        if classification.durability not in {
            EpisodeDurability.DURABLE,
            EpisodeDurability.TEMPORARY,
        }:
            return [
                _classification_rejection(
                    f"classification:durability:{classification.durability.value}"
                )
            ]
        if classification.sensitivity == Sensitivity.SECRET:
            return [_classification_rejection("classification:secret")]
        if not extraction.candidates:
            return [_classification_rejection("classification:no_candidates")]

        decisions: list[CandidatePromotionDecision] = []
        for index, candidate in enumerate(extraction.candidates):
            promotion_score = promotion_score_for_candidate(
                candidate=candidate,
                durability=classification.durability,
            )
            rejection_reason = self._rejection_reason(
                candidate=candidate,
                episode_content=episode_content,
                sensitivity=classification.sensitivity,
                durability=classification.durability,
                promotion_score=promotion_score,
            )
            decisions.append(
                CandidatePromotionDecision(
                    candidate_index=index,
                    candidate=candidate,
                    status=CandidateStageStatus.REJECTED
                    if rejection_reason is not None
                    else CandidateStageStatus.STAGED,
                    promotion_score=promotion_score,
                    rejection_reason=rejection_reason,
                )
            )
        return decisions

    def candidates_for_episode(
        self,
        *,
        extraction: ExtractionResult,
        episode_content: str,
    ) -> list[ExtractedMemoryCandidate]:
        return [
            decision.candidate
            for decision in self.decisions_for_episode(
                extraction=extraction,
                episode_content=episode_content,
            )
            if decision.should_promote and decision.candidate is not None
        ]

    def _rejection_reason(
        self,
        *,
        candidate: ExtractedMemoryCandidate,
        episode_content: str,
        sensitivity: Sensitivity,
        durability: EpisodeDurability,
        promotion_score: float,
    ) -> str | None:
        if candidate.operation_hint == MemoryOperation.NOOP:
            return "candidate:noop"
        if candidate.confidence < MIN_EXTRACTED_CONFIDENCE:
            return "candidate:low_confidence"
        if candidate.importance < MIN_EXTRACTED_IMPORTANCE:
            return "candidate:low_importance"
        if not evidence_quote_matches(episode_content, candidate.evidence_quote):
            return "candidate:evidence_quote_missing"
        if sensitivity == Sensitivity.POSSIBLE_SECRET and contains_secret_like_text(
            f"{candidate.content}\n{candidate.evidence_quote}"
        ):
            return "candidate:possible_secret"
        if durability == EpisodeDurability.TEMPORARY and candidate.valid_until is None:
            return "candidate:temporary_without_valid_until"
        if (
            candidate.criticality != Criticality.MUST_INCLUDE
            and promotion_score < PROMOTION_SCORE_THRESHOLD
        ):
            return "candidate:low_promotion_score"
        return None


def evidence_quote_matches(episode_content: str, evidence_quote: str) -> bool:
    normalized_episode = _normalize_for_evidence_match(episode_content)
    normalized_quote = _normalize_for_evidence_match(evidence_quote)
    return bool(normalized_quote) and normalized_quote in normalized_episode


def contains_secret_like_text(text: str) -> bool:
    return any(pattern.search(text) for pattern in _SECRET_PATTERNS)


def embedding_text_for_candidate(candidate: ExtractedMemoryCandidate) -> str:
    if candidate.embedding_text:
        return candidate.embedding_text
    return f"{candidate.subject} {candidate.key}: {candidate.content}"


def promotion_score_for_candidate(
    *,
    candidate: ExtractedMemoryCandidate,
    durability: EpisodeDurability,
) -> float:
    score = 0.0
    if durability == EpisodeDurability.DURABLE:
        score += 0.26
    elif durability == EpisodeDurability.TEMPORARY:
        score += 0.18

    score += candidate.importance * 0.25
    score += candidate.confidence * 0.25

    if candidate.criticality == Criticality.MUST_INCLUDE:
        score += 0.18
    elif candidate.criticality == Criticality.HIGH_PRIORITY:
        score += 0.1

    if candidate.evidence_role in {EvidenceRole.STATED, EvidenceRole.CORRECTED}:
        score += 0.04
    elif candidate.evidence_role == EvidenceRole.OBSERVED:
        score += 0.03
    elif candidate.evidence_role == EvidenceRole.INFERRED:
        score -= 0.05

    if candidate.operation_hint in {MemoryOperation.SUPERSEDE, MemoryOperation.CONTEST}:
        score += 0.04
    if candidate.applicability:
        score += 0.03
    if _looks_vague(candidate.content):
        score -= 0.12

    return max(0.0, min(1.0, round(score, 4)))


def _classification_rejection(reason: str) -> CandidatePromotionDecision:
    return CandidatePromotionDecision(
        candidate_index=-1,
        candidate=None,
        status=CandidateStageStatus.REJECTED,
        promotion_score=0.0,
        rejection_reason=reason,
    )


def _normalize_for_evidence_match(text: str) -> str:
    return " ".join(text.casefold().split())


def _looks_vague(content: str) -> bool:
    normalized = content.casefold().strip()
    if len(normalized.split()) < 4:
        return True
    vague_phrases = (
        "talked about",
        "discussed",
        "mentioned something",
        "some information",
        "the user said something",
    )
    return any(phrase in normalized for phrase in vague_phrases)
