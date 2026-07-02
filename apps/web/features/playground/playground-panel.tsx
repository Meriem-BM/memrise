"use client";

import { useMutation } from "@tanstack/react-query";
import { Send, ThumbsUp } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { getMemoryClient } from "@/lib/api";

export function PlaygroundPanel() {
  const client = getMemoryClient();
  const [message, setMessage] = useState(
    "Atlaused npm before, but we now use pnpm. Never edit its generated lockfile manually.",
  );
  const [query, setQuery] = useState("How should I install dependencies for Atlas?");
  const [retrievalId, setRetrievalId] = useState<string | null>(null);
  const [memoryVersionId, setMemoryVersionId] = useState<string | null>(null);

  const capture = useMutation({
    mutationFn: () =>
      client.capture({
        namespace_id: "demo",
        agent_id: "coding-agent",
        session_id: "session-1",
        user_id: "user-1",
        project_id: "atlas",
        events: [{ kind: "user_message", content: message, metadata: {} }],
      }),
  });
  const retrieve = useMutation({
    mutationFn: () =>
      client.retrieve({
        namespace_id: "demo",
        agent_id: "coding-agent",
        user_id: "user-1",
        project_id: "atlas",
        query,
        task_type: "dependency_install",
        token_budget: 800,
        limit: 10,
        graph_hops: 1,
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
        memory_version_id: memoryVersionId,
      });
    },
  });

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
      <Card>
        <CardTitle>Capture</CardTitle>
        <Textarea
          className="mt-3"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
        />
        <Button
          className="mt-3 gap-2"
          onClick={() => capture.mutate()}
          disabled={capture.isPending}
        >
          <Send size={16} />
          Capture
        </Button>
        {capture.data ? (
          <pre className="mt-3 overflow-auto text-xs">{JSON.stringify(capture.data, null, 2)}</pre>
        ) : null}
      </Card>
      <Card>
        <CardTitle>Retrieve</CardTitle>
        <Input className="mt-3" value={query} onChange={(event) => setQuery(event.target.value)} />
        <div className="mt-3 flex gap-2">
          <Button onClick={() => retrieve.mutate()} disabled={retrieve.isPending}>
            Retrieve
          </Button>
          <Button
            className="gap-2 bg-slate-800"
            onClick={() => feedback.mutate()}
            disabled={!retrievalId}
          >
            <ThumbsUp size={16} />
            Helpful
          </Button>
        </div>
        {retrieve.data ? (
          <pre className="mt-3 max-h-96 overflow-auto text-xs">
            {JSON.stringify(retrieve.data, null, 2)}
          </pre>
        ) : null}
        {feedback.data ? (
          <pre className="mt-3 overflow-auto text-xs">{JSON.stringify(feedback.data, null, 2)}</pre>
        ) : null}
      </Card>
    </div>
  );
}
