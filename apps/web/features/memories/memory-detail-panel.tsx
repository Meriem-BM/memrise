"use client";

import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
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
  return (
    <div className="grid gap-4">
      <Card>
        <CardTitle>Memory</CardTitle>
        {detail.data?.current_version ? (
          <div className="mt-3">
            <div className="flex flex-wrap gap-2">
              <Badge>{detail.data.current_version.type}</Badge>
              <Badge>{detail.data.current_version.status}</Badge>
              <Badge>{detail.data.current_version.criticality}</Badge>
            </div>
            <p className="mt-3">{detail.data.current_version.content}</p>
          </div>
        ) : (
          <p className="mt-3 text-sm text-slate-500">No current version found.</p>
        )}
      </Card>
      {detail.data?.graph_edges?.length ? (
        <Card>
          <CardTitle>Graph Edges</CardTitle>
          <div className="mt-3 space-y-2">
            {detail.data.graph_edges.map((edge) => (
              <div
                key={String(edge.id)}
                className="rounded border border-slate-200 px-3 py-2 text-sm text-slate-700"
              >
                <span className="font-medium">{String(edge.relation)}</span>
                <span className="text-slate-500">
                  {" "}
                  {String(edge.source_node_id)} → {String(edge.target_node_id)}
                </span>
              </div>
            ))}
          </div>
        </Card>
      ) : null}
      <Card>
        <CardTitle>History And Provenance</CardTitle>
        <pre className="mt-3 max-h-[34rem] overflow-auto text-xs">
          {JSON.stringify(detail.data ?? {}, null, 2)}
        </pre>
      </Card>
    </div>
  );
}
