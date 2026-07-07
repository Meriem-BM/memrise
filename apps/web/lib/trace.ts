import type { CandidateStageSummary, JobSummary } from "memrise-memory-sdk";

export type TraceDecision = "ok" | "rejected" | "pending" | "failed" | "info";

export type TraceStep = {
  id: string;
  label: string;
  decision: TraceDecision;
  reasonCode?: string;
  error?: string;
  score?: number;
  detail?: unknown;
  href?: string;
};

const REASONS: Record<string, string> = {
  "classification:no_extract": "classifier saw nothing durable",
  "classification:secret": "content classified as a secret",
  "classification:no_candidates": "classifier accepted but produced no candidates",
  "candidate:noop": "provider marked this a no-op",
  "candidate:low_confidence": "confidence below the 0.35 floor",
  "candidate:low_importance": "importance below the 0.15 floor",
  "candidate:evidence_quote_missing": "evidence quote not found in the episode",
  "candidate:possible_secret": "candidate text looks like a secret",
  "candidate:temporary_without_valid_until": "temporary memory missing valid_until",
  "candidate:low_promotion_score": "promotion score below the 0.58 threshold",
  "reconcile:noop": "reconciler decided nothing changed",
  "reconcile:deleted": "logical memory was deleted; not reactivated",
  "reconcile:historical_duplicate": "duplicate of a historical version",
  "candidate:no_memory_applied": "no memory was applied for this candidate",
};

export function humanizeReason(code: string): string {
  return REASONS[code] ?? code;
}

export function buildCaptureTrace(input: {
  skippedExtraction: boolean;
  jobs: JobSummary[];
  candidates: CandidateStageSummary[];
}): TraceStep[] {
  if (input.skippedExtraction) {
    return [
      {
        id: "gate",
        label: "Gate: extraction skipped",
        decision: "info",
        detail: "Content below the minimum size for durable knowledge.",
      },
    ];
  }

  const steps: TraceStep[] = input.jobs.map((job) => ({
    id: job.id,
    label: `Extraction job · ${job.status}`,
    decision: job.status === "completed" ? "ok" : job.status === "failed" ? "failed" : "pending",
    error: job.status === "failed" ? (job.last_error ?? undefined) : undefined,
    detail: job,
  }));

  const classification = input.candidates[0]?.classification;
  if (classification) {
    const parts = [classification.durability, classification.sensitivity]
      .filter(Boolean)
      .join(" · ");
    steps.push({
      id: "classification",
      label: `Classification: ${parts || "unknown"}`,
      decision: "info",
      detail: classification,
    });
  }

  for (const candidate of input.candidates) {
    const promoted = candidate.status === "promoted";
    steps.push({
      id: candidate.id,
      label: promoted
        ? `${candidate.subject ?? "memory"} · ${(candidate.key ?? "").replaceAll("_", " ")}`
        : `Candidate ${candidate.candidate_index + 1} rejected`,
      decision: promoted ? "ok" : candidate.status === "failed" ? "failed" : "rejected",
      reasonCode: candidate.rejection_reason ?? undefined,
      score: promoted ? candidate.promotion_score : undefined,
      detail: candidate,
    });
  }
  return steps;
}
