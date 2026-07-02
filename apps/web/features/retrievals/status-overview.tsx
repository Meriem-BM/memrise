"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, Database, History } from "lucide-react";
import type { components } from "memrise-memory-sdk";

import { Badge } from "@/components/ui/badge";
import { Card, CardTitle } from "@/components/ui/card";
import { getMemriseClient } from "@/lib/api";
import { formatCount } from "@/lib/format";
import { LOCAL_INSPECTOR_SCOPE } from "@/lib/scope";

type MemorySummary = components["schemas"]["MemorySummary"];

export function StatusOverview() {
  const client = getMemriseClient();
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => client.healthReady(),
    retry: false,
  });
  const memories = useQuery({
    queryKey: ["memories", "local"],
    queryFn: () =>
      client.listMemories({
        namespaceId: LOCAL_INSPECTOR_SCOPE.namespaceId,
        agentId: LOCAL_INSPECTOR_SCOPE.agentId,
        projectId: LOCAL_INSPECTOR_SCOPE.projectId,
      }),
    retry: false,
  });
  const rows = memories.data ?? [];
  const active = rows.filter((row: MemorySummary) => row.status === "active").length;
  const contested = rows.filter((row: MemorySummary) => row.status === "contested").length;
  const critical = rows.filter((row: MemorySummary) => row.criticality === "must_include").length;

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card>
        <div className="flex items-center gap-2 text-slate-500">
          <Activity size={18} />
          <CardTitle>Service</CardTitle>
        </div>
        <p className="mt-4 text-3xl font-semibold">{health.data?.status ?? "unknown"}</p>
        <Badge className="mt-3">{health.data?.database ?? "not checked"}</Badge>
      </Card>
      <Card>
        <div className="flex items-center gap-2 text-slate-500">
          <Database size={18} />
          <CardTitle>Memories</CardTitle>
        </div>
        <dl className="mt-4 grid grid-cols-3 gap-3 text-sm">
          <Metric label="active" value={active} />
          <Metric label="critical" value={critical} />
          <Metric label="contested" value={contested} />
        </dl>
      </Card>
      <Card>
        <div className="flex items-center gap-2 text-slate-500">
          <History size={18} />
          <CardTitle>Recent Retrievals</CardTitle>
        </div>
        <p className="mt-4 text-sm text-slate-600">
          Retrieval traces appear after the playground or API returns memory context.
        </p>
      </Card>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-2xl font-semibold">{formatCount(value)}</dd>
    </div>
  );
}
