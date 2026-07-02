"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import type { components } from "memrise-memory-sdk";

import { Badge } from "@/components/ui/badge";
import { Card, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getMemriseClient } from "@/lib/api";
import { LOCAL_INSPECTOR_SCOPE } from "@/lib/scope";

type MemorySummary = components["schemas"]["MemorySummary"];

export function MemoriesPanel() {
  const client = getMemriseClient();
  const memories = useQuery({
    queryKey: ["memories", "list"],
    queryFn: () =>
      client.listMemories({
        namespaceId: LOCAL_INSPECTOR_SCOPE.namespaceId,
        agentId: LOCAL_INSPECTOR_SCOPE.agentId,
        projectId: LOCAL_INSPECTOR_SCOPE.projectId,
      }),
    retry: false,
  });
  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <CardTitle>Memories</CardTitle>
        <Input className="max-w-xs" placeholder="Filter" />
      </div>
      <div className="mt-4 divide-y divide-slate-200">
        {(memories.data ?? []).map((memory: MemorySummary) => (
          <Link
            key={memory.memory_id}
            href={`/memories/${memory.memory_id}`}
            className="block py-3"
          >
            <div className="flex flex-wrap items-center gap-2">
              <strong>{memory.subject}</strong>
              <Badge>{memory.type}</Badge>
              <Badge>{memory.status}</Badge>
              <Badge>{memory.criticality}</Badge>
            </div>
            <p className="mt-1 text-sm text-slate-600">{memory.content}</p>
          </Link>
        ))}
        {memories.data?.length === 0 ? (
          <p className="py-8 text-sm text-slate-500">No memories yet.</p>
        ) : null}
      </div>
    </Card>
  );
}
