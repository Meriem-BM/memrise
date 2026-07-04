import type { CandidateStageSummary, JobSummary } from "memrise-memory-sdk";

import type { RetrievalRow } from "@/lib/retrieve";

export type RecallResult = {
  status: "pending" | "done" | "error";
  skipped?: boolean;
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

export type AnswerResult = {
  status: "pending" | "done" | "error";
  text?: string;
  modelName?: string;
  promptVersion?: string;
  memoryEnabled?: boolean;
  error?: string;
};

export type ConsoleEntry =
  | {
      kind: "turn";
      id: string;
      prompt: string;
      memoryEnabled: boolean;
      answer: AnswerResult;
      recall: RecallResult;
      learn: LearnResult;
    }
  | { kind: "notice"; id: string; text: string };

export function promotedSubject(learn: LearnResult): string | null {
  const candidate = (learn.candidates ?? []).find((item) => item.status === "promoted");
  return candidate?.subject ?? null;
}

function firstPromoted(learn: LearnResult): CandidateStageSummary | undefined {
  return (learn.candidates ?? []).find((item) => item.status === "promoted");
}

export function turnSummary(
  answer: AnswerResult,
  recall: RecallResult,
  learn: LearnResult,
): string {
  if (answer.status === "pending" || recall.status === "pending" || learn.status === "pending") {
    return "thinking…";
  }
  const answerPart =
    answer.status === "error"
      ? "answer failed"
      : answer.memoryEnabled === false
        ? "answered without Memrise"
        : "answered with Memrise";
  const recallPart =
    recall.status === "error"
      ? "recall failed"
      : recall.skipped
        ? "recall off"
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
  return `${answerPart} · ${recallPart} · ${learnPart}`;
}
