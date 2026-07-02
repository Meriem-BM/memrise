"use client";

import { useMutation } from "@tanstack/react-query";
import { Loader2, Send, ThumbsUp } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  CaptureOutcomePanel,
  type CaptureJob,
  type CaptureOutcome,
} from "@/features/playground/capture-outcome-panel";
import { getMemriseClient } from "@/lib/api";
import { LOCAL_INSPECTOR_SCOPE } from "@/lib/scope";

export function PlaygroundPanel() {
  const client = getMemriseClient();
  const [message, setMessage] = useState(
    "Atlaused npm before, but we now use pnpm. Never edit its generated lockfile manually.",
  );
  const [query, setQuery] = useState("How should I install dependencies for Atlas?");
  const [retrievalId, setRetrievalId] = useState<string | null>(null);
  const [memoryVersionId, setMemoryVersionId] = useState<string | null>(null);

  const capture = useMutation({
    mutationFn: async (): Promise<CaptureOutcome> => {
      const startedAt = Date.now();
      const captureResult = await client.capture({
        ...LOCAL_INSPECTOR_SCOPE,
        events: [{ kind: "user_message", content: message, metadata: {} }],
      });

      if (captureResult.job_ids.length === 0) {
        return {
          episodeIds: captureResult.episode_ids,
          jobs: [],
          memories: [],
          skippedExtraction: true,
        };
      }

      const jobs: CaptureJob[] = [];
      for (const jobId of captureResult.job_ids) {
        const job = await client.waitForJob(jobId, { timeoutMs: 120_000, pollMs: 500 });
        jobs.push({
          id: job.id,
          type: job.type,
          status: job.status,
          last_error: job.last_error,
        });
      }

      const listed = await client.listMemories({
        namespaceId: LOCAL_INSPECTOR_SCOPE.namespaceId,
        agentId: LOCAL_INSPECTOR_SCOPE.agentId,
        projectId: LOCAL_INSPECTOR_SCOPE.projectId,
      });
      const memories = listed
        .filter((memory) => Date.parse(memory.created_at) >= startedAt - 5_000)
        .map((memory) => ({
          memory_id: memory.memory_id,
          subject: memory.subject,
          key: memory.key,
          content: memory.content,
          status: memory.status,
          type: memory.type,
        }));

      return {
        episodeIds: captureResult.episode_ids,
        jobs,
        memories,
        skippedExtraction: false,
      };
    },
  });

  const retrieve = useMutation({
    mutationFn: () =>
      client.retrieve({
        ...LOCAL_INSPECTOR_SCOPE,
        query,
        taskType: "dependency_install",
        tokenBudget: 800,
        limit: 10,
        graphHops: 1,
      }),
    onSuccess: (data) => {
      setRetrievalId(data.retrieval_id);
      setMemoryVersionId(
        data.memories[0]?.memory_version_id ?? data.critical[0]?.memory_version_id ?? null,
      );
    },
  });

  const feedback = useMutation({
    mutationFn: () => {
      if (!retrievalId || !memoryVersionId) {
        throw new Error("retrieve memory before feedback");
      }
      return client.feedback(retrievalId, {
        outcome: "helpful",
        source: "developer",
        memoryVersionId: memoryVersionId,
      });
    },
  });

  return (
    <div>
      <PageHeader
        eyebrow="Live Sandbox"
        title="Playground"
        description="Feed Memrise a message, watch it distill knowledge, then retrieve it back — the full capture → extract → recall loop, live."
      />
      <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <Card className="animate-rise">
          <CardTitle>Capture</CardTitle>
          <Textarea
            className="mt-3"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
          />
          <Button className="mt-3" onClick={() => capture.mutate()} disabled={capture.isPending}>
            {capture.isPending ? (
              <Loader2 className="animate-spin" size={16} />
            ) : (
              <Send size={16} />
            )}
            {capture.isPending ? "Extracting…" : "Capture"}
          </Button>
          {capture.isError ? (
            <p className="mt-3 text-sm text-danger">{capture.error.message}</p>
          ) : null}
          {capture.data ? <CaptureOutcomePanel outcome={capture.data} /> : null}
        </Card>
        <Card className="animate-rise" style={{ animationDelay: "80ms" }}>
          <CardTitle>Retrieve</CardTitle>
          <Input
            className="mt-3"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <div className="mt-3 flex gap-2">
            <Button onClick={() => retrieve.mutate()} disabled={retrieve.isPending}>
              {retrieve.isPending ? <Loader2 className="animate-spin" size={16} /> : null}
              Retrieve
            </Button>
            <Button variant="ghost" onClick={() => feedback.mutate()} disabled={!retrievalId}>
              <ThumbsUp size={16} />
              Helpful
            </Button>
          </div>
          {retrieve.isError ? (
            <p className="mt-3 text-sm text-danger">{retrieve.error.message}</p>
          ) : null}
          {retrieve.data ? <JsonBlock value={retrieve.data} className="max-h-96" /> : null}
          {feedback.isError ? (
            <p className="mt-3 text-sm text-danger">{feedback.error.message}</p>
          ) : null}
          {feedback.data ? <JsonBlock value={feedback.data} /> : null}
        </Card>
      </div>
    </div>
  );
}

function JsonBlock({ value, className = "" }: { value: unknown; className?: string }) {
  return (
    <pre
      className={`mt-3 overflow-auto rounded-lg border border-border bg-black p-3 font-mono text-xs leading-relaxed text-muted ${className}`}
    >
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}
