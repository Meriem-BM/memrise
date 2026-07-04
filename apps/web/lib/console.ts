import type { CandidateStageSummary, JobSummary } from "memrise-memory-sdk";

import type { RetrievalRow } from "@/lib/retrieve";

export type RecallResult = {
  status: "pending" | "done" | "error";
  retrievalId?: string;
  rows?: RetrievalRow[];
  usedTokens?: number;
  tokenBudget?: number;
  error?: string;
};

export type LearnResult = {
  status: "pending" | "done" | "error";
  skipped?: boolean;
  jobs?: JobSummary[];
  candidates?: CandidateStageSummary[];
  error?: string;
};

export type ConsoleEntry =
  | { kind: "turn"; id: string; prompt: string; recall: RecallResult; learn: LearnResult }
  | { kind: "notice"; id: string; text: string };

export function promotedSubject(learn: LearnResult): string | null {
  const candidate = (learn.candidates ?? []).find((item) => item.status === "promoted");
  return candidate?.subject ?? null;
}

function firstPromoted(learn: LearnResult): CandidateStageSummary | undefined {
  return (learn.candidates ?? []).find((item) => item.status === "promoted");
}

export function turnSummary(recall: RecallResult, learn: LearnResult): string {
  if (recall.status === "pending" || learn.status === "pending") {
    return "thinking…";
  }
  const recallPart =
    recall.status === "error"
      ? "recall failed"
      : (recall.rows?.length ?? 0) > 0
        ? `recalled ${recall.rows?.length}`
        : "nothing recalled";
  const promoted = firstPromoted(learn);
  const learnPart =
    learn.status === "error"
      ? "learn failed"
      : learn.skipped
        ? "extraction skipped"
        : promoted
          ? `learned ${promoted.subject} · ${promoted.key}`
          : "nothing learned";
  return `${recallPart} · ${learnPart}`;
}
