"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/page-header";
import { Badge, statusVariant } from "@/components/ui/badge";
import { Card, CardTitle } from "@/components/ui/card";
import { getMemriseClient } from "@/lib/api";

type Props = {
  memoryId: string;
};

export function MemoryDetailPanel({ memoryId }: Props) {
  const client = getMemriseClient();
  const detail = useQuery({
    queryKey: ["memory", memoryId],
    queryFn: () => client.explain(memoryId),
    retry: false,
  });

  const current = detail.data?.current_version;

  return (
    <div>
      <Link
        href="/memories"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted transition-colors hover:text-foreground"
      >
        <ArrowLeft size={15} /> Back to memories
      </Link>
      <PageHeader
        eyebrow="Provenance"
        title={current?.subject ?? "Memory"}
        description="The current canonical version, its graph relationships, and the full history behind it."
      />

      <div className="grid gap-4">
        <Card className="animate-rise">
          <CardTitle>Current Version</CardTitle>
          {current ? (
            <div className="mt-4">
              <div className="flex flex-wrap gap-2">
                <Badge>{current.type}</Badge>
                <Badge variant={statusVariant(current.status)}>{current.status}</Badge>
                <Badge variant={statusVariant(current.criticality)}>{current.criticality}</Badge>
              </div>
              <p className="mt-4 text-[15px] leading-relaxed text-foreground">{current.content}</p>
            </div>
          ) : (
            <p className="mt-3 text-sm text-muted">No current version found.</p>
          )}
        </Card>

        {detail.data?.graph_edges?.length ? (
          <Card className="animate-rise" style={{ animationDelay: "80ms" }}>
            <CardTitle>Graph Edges</CardTitle>
            <div className="mt-4 space-y-2">
              {detail.data.graph_edges.map((edge) => (
                <div
                  key={String(edge.id)}
                  className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-white/2 px-3 py-2 text-sm"
                >
                  <Badge variant="inverted">{String(edge.relation)}</Badge>
                  <span className="font-mono text-xs text-muted">
                    {String(edge.source_node_id)} <span className="text-white/60">→</span>{" "}
                    {String(edge.target_node_id)}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        ) : null}

        <Card className="animate-rise" style={{ animationDelay: "160ms" }}>
          <CardTitle>History &amp; Provenance</CardTitle>
          <pre className="mt-3 max-h-[34rem] overflow-auto rounded-lg border border-border bg-black p-3 font-mono text-xs leading-relaxed text-muted">
            {JSON.stringify(detail.data ?? {}, null, 2)}
          </pre>
        </Card>
      </div>
    </div>
  );
}
