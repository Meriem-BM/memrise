"use client";

import { Loader2, Send, ThumbsUp } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { CaptureOutcomePanel } from "@/features/playground/capture-outcome-panel";
import { usePlaygroundCapture } from "@/hooks/usePlaygroundCapture";
import { usePlaygroundRecall } from "@/hooks/usePlaygroundRecall";

export function PlaygroundPanel() {
  const { message, setMessage, capture } = usePlaygroundCapture();
  const { query, setQuery, retrievalId, retrieve, feedback } = usePlaygroundRecall();

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
