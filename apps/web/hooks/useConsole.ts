"use client";

import { useMutation } from "@tanstack/react-query";
import { useCallback, useState } from "react";

import { getMemriseClient } from "@/lib/api";
import {
  promotedSubject,
  type AnswerResult,
  type ConsoleEntry,
  type LearnResult,
  type RecallResult,
} from "@/lib/console";
import { buildRetrievalRows } from "@/lib/retrieve";
import { LOCAL_INSPECTOR_SCOPE } from "@/lib/scope";

const scope = {
  namespaceId: LOCAL_INSPECTOR_SCOPE.namespaceId,
  agentId: LOCAL_INSPECTOR_SCOPE.agentId,
  userId: LOCAL_INSPECTOR_SCOPE.userId,
  projectId: LOCAL_INSPECTOR_SCOPE.projectId,
};

function newSessionId(): string {
  return `session-${Date.now().toString(36)}`;
}

export function useConsole() {
  const client = getMemriseClient();
  const [sessionId, setSessionId] = useState(newSessionId);
  const [entries, setEntries] = useState<ConsoleEntry[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [graphQuery, setGraphQuery] = useState<{ query: string; nonce: number } | null>(null);
  const [feedbackScores, setFeedbackScores] = useState<Record<string, number>>({});
  const [memriseEnabled, setMemriseEnabled] = useState(true);

  const patchTurn = useCallback(
    (
      id: string,
      changes: Partial<{ answer: AnswerResult; recall: RecallResult; learn: LearnResult }>,
    ) => {
      setEntries((current) =>
        current.map((entry) =>
          entry.kind === "turn" && entry.id === id ? { ...entry, ...changes } : entry,
        ),
      );
    },
    [],
  );

  const submit = useCallback(
    async (prompt: string) => {
      const id = crypto.randomUUID();
      const useMemory = memriseEnabled;
      setEntries((current) => [
        ...current,
        {
          kind: "turn",
          id,
          prompt,
          memoryEnabled: useMemory,
          answer: { status: "pending" },
          recall: useMemory ? { status: "pending" } : { status: "done", skipped: true, rows: [] },
          learn: useMemory
            ? { status: "pending" }
            : { status: "done", skipped: true, jobs: [], candidates: [] },
        },
      ]);
      setSelectedId(id);

      const responseTask = (async () => {
        try {
          const response = await client.respond({ ...scope, query: prompt, useMemory });
          const retrieval = response.retrieval;
          const detail = retrieval ? await client.getRetrieval(retrieval.retrieval_id) : null;
          patchTurn(id, {
            answer: {
              status: "done",
              text: response.answer,
              modelName: response.model_name,
              promptVersion: response.prompt_version,
              memoryEnabled: response.memory_enabled,
            },
            recall: retrieval
              ? {
                  status: "done",
                  retrievalId: retrieval.retrieval_id,
                  rows: buildRetrievalRows(retrieval, detail?.items ?? []),
                  usedTokens: retrieval.used_tokens,
                  tokenBudget: retrieval.token_budget,
                }
              : { status: "done", skipped: true, rows: [] },
          });
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          patchTurn(id, {
            answer: {
              status: "error",
              error: message,
              memoryEnabled: useMemory,
            },
            recall: useMemory
              ? {
                  status: "error",
                  error: message,
                }
              : { status: "done", skipped: true, rows: [] },
          });
        }
      })();

      const learnTask = (async () => {
        if (!useMemory) return;
        try {
          const result = await client.capture({
            ...scope,
            sessionId,
            events: [{ kind: "user_message", content: prompt, metadata: {} }],
          });
          if (result.job_ids.length === 0) {
            patchTurn(id, { learn: { status: "done", skipped: true, jobs: [], candidates: [] } });
            return;
          }
          const jobs = [];
          for (const jobId of result.job_ids) {
            jobs.push(await client.waitForJob(jobId, { timeoutMs: 120_000, pollMs: 500 }));
          }
          const episodeId = result.episode_ids[0];
          const candidates = episodeId ? await client.listEpisodeCandidates(episodeId) : [];
          const learn: LearnResult = { status: "done", jobs, candidates };
          patchTurn(id, { learn });
          const subject = promotedSubject(learn);
          if (subject) setGraphQuery({ query: subject, nonce: Date.now() });
        } catch (error) {
          patchTurn(id, {
            learn: {
              status: "error",
              error: error instanceof Error ? error.message : String(error),
            },
          });
        }
      })();

      await Promise.allSettled([responseTask, learnTask]);
    },
    [client, memriseEnabled, patchTurn, sessionId],
  );

  const newSession = useCallback(() => {
    const previous = sessionId;
    const hadTurns = entries.some((entry) => entry.kind === "turn");
    setSessionId(newSessionId());
    setEntries((current) => [
      ...current,
      { kind: "notice", id: crypto.randomUUID(), text: "— new session —" },
    ]);
    if (!hadTurns) return;
    void client
      .consolidate(previous, { ...scope, sessionId: previous })
      .then((result) =>
        setEntries((current) => [
          ...current,
          {
            kind: "notice",
            id: crypto.randomUUID(),
            text: `previous session consolidating → job ${result.job_id}`,
          },
        ]),
      )
      .catch(() => undefined);
  }, [client, entries, sessionId]);

  const feedbackFor = useMutation({
    mutationFn: async (input: {
      retrievalId: string;
      memoryVersionId: string;
      outcome: "helpful" | "harmful";
    }) => {
      const result = await client.feedback(input.retrievalId, {
        outcome: input.outcome,
        source: "developer",
        memoryVersionId: input.memoryVersionId,
      });
      if (result.usefulness_score != null) {
        setFeedbackScores((current) => ({
          ...current,
          [input.memoryVersionId]: result.usefulness_score as number,
        }));
      }
      return result;
    },
  });

  const select = useCallback((id: string) => setSelectedId(id), []);

  return {
    sessionId,
    entries,
    selectedId,
    select,
    submit,
    newSession,
    memriseEnabled,
    setMemriseEnabled,
    feedbackFor,
    feedbackScores,
    graphQuery,
  };
}
