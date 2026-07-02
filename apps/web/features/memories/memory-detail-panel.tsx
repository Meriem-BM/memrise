"use client";

import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Card, CardTitle } from "@/components/ui/card";
import { getMemoryClient } from "@/lib/api";

type Props = {
  memoryId: string;
};

export function MemoryDetailPanel({ memoryId }: Props) {
  const client = getMemoryClient();
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
      <Card>
        <CardTitle>History And Provenance</CardTitle>
        <pre className="mt-3 max-h-[34rem] overflow-auto text-xs">
          {JSON.stringify(detail.data ?? {}, null, 2)}
        </pre>
      </Card>
    </div>
  );
}
