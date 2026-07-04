"use client";

import { ThumbsDown, ThumbsUp } from "lucide-react";

import { PipelineTrace } from "@/components/trace/pipeline-trace";
import { ScoreBar } from "@/components/trace/score-bar";
import type { ConsoleEntry } from "@/lib/console";
import { buildCaptureTrace } from "@/lib/trace";
import type { useConsole } from "@/hooks/useConsole";

type Turn = Extract<ConsoleEntry, { kind: "turn" }>;
type FeedbackMutation = ReturnType<typeof useConsole>["feedbackFor"];

export function TracePanel({
  turn,
  feedbackFor,
  feedbackScores,
}: {
  turn: Turn | null;
  feedbackFor: FeedbackMutation;
  feedbackScores: Record<string, number>;
}) {
  return (
    <section className="flex-1 overflow-y-auto rounded-2xl border border-border bg-white/2 p-4">
      <h2 className="font-mono text-[11px] uppercase tracking-widest text-faint">Trace</h2>
      {!turn ? (
        <p className="mt-3 text-sm text-muted">Select a turn to see its story.</p>
      ) : (
        <div className="mt-3 space-y-5">
          <div>
            <h3 className="text-sm font-medium">Recall</h3>
            {turn.recall.status === "pending" ? (
              <p className="mt-2 text-sm text-muted">retrieving…</p>
            ) : turn.recall.status === "error" ? (
              <p className="mt-2 text-sm text-danger">{turn.recall.error}</p>
            ) : (turn.recall.rows?.length ?? 0) === 0 ? (
              <p className="mt-2 text-sm text-muted">nothing relevant in memory yet.</p>
            ) : (
              <div className="mt-2 space-y-3">
                {turn.recall.rows?.map((row) => (
                  <div
                    key={row.memory.memory_version_id}
                    className="rounded-lg border border-border bg-white/2 p-3"
                  >
                    <p className="text-sm leading-relaxed">{row.memory.content}</p>
                    <div className="mt-2 space-y-1">
                      {row.scores.lexical !== undefined ? (
                        <ScoreBar label="lexical" value={row.scores.lexical} />
                      ) : null}
                      {row.scores.semantic !== undefined ? (
                        <ScoreBar label="semantic" value={row.scores.semantic} />
                      ) : null}
                      {row.scores.graph !== undefined ? (
                        <ScoreBar label="graph" value={row.scores.graph} />
                      ) : null}
                    </div>
                    <div className="mt-2 flex items-center gap-2">
                      <FeedbackButton
                        icon="up"
                        onClick={() =>
                          turn.recall.retrievalId &&
                          feedbackFor.mutate({
                            retrievalId: turn.recall.retrievalId,
                            memoryVersionId: row.memory.memory_version_id,
                            outcome: "helpful",
                          })
                        }
                      />
                      <FeedbackButton
                        icon="down"
                        onClick={() =>
                          turn.recall.retrievalId &&
                          feedbackFor.mutate({
                            retrievalId: turn.recall.retrievalId,
                            memoryVersionId: row.memory.memory_version_id,
                            outcome: "harmful",
                          })
                        }
                      />
                      {feedbackScores[row.memory.memory_version_id] !== undefined ? (
                        <span className="font-mono text-xs text-muted">
                          usefulness → {feedbackScores[row.memory.memory_version_id].toFixed(2)}
                        </span>
                      ) : null}
                      {feedbackFor.isError &&
                      feedbackFor.variables?.memoryVersionId === row.memory.memory_version_id ? (
                        <span className="text-xs text-danger">{feedbackFor.error.message}</span>
                      ) : null}
                    </div>
                  </div>
                ))}
                {turn.recall.usedTokens !== undefined ? (
                  <p className="font-mono text-xs text-faint">
                    {turn.recall.usedTokens} / {turn.recall.tokenBudget} tokens in context
                  </p>
                ) : null}
              </div>
            )}
          </div>

          <div>
            <h3 className="text-sm font-medium">Learn</h3>
            {turn.learn.status === "pending" ? (
              <p className="mt-2 text-sm text-muted">extracting…</p>
            ) : turn.learn.status === "error" ? (
              <p className="mt-2 text-sm text-danger">{turn.learn.error}</p>
            ) : (
              <div className="mt-2">
                <PipelineTrace
                  steps={buildCaptureTrace({
                    skippedExtraction: turn.learn.skipped ?? false,
                    jobs: turn.learn.jobs ?? [],
                    candidates: turn.learn.candidates ?? [],
                  })}
                />
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

function FeedbackButton({ icon, onClick }: { icon: "up" | "down"; onClick: () => void }) {
  const Icon = icon === "up" ? ThumbsUp : ThumbsDown;
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-full border border-white/10 p-1.5 text-white/50 transition-colors hover:text-white"
      aria-label={icon === "up" ? "helpful" : "harmful"}
    >
      <Icon size={13} />
    </button>
  );
}
