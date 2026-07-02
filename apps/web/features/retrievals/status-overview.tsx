"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, Database, History } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import { formatCount } from "@/lib/format";

type MemorySummary = {
  status: string;
  criticality: string;
};

export function StatusOverview() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => apiFetch<{ status: string; database?: string }>("/health/ready"),
    retry: false,
  });
  const memories = useQuery({
    queryKey: ["memories", "demo"],
    queryFn: () =>
      apiFetch<MemorySummary[]>(
        "/v1/memories?namespace_id=demo&agent_id=coding-agent&project_id=atlas",
      ),
    retry: false,
  });
  const rows = memories.data ?? [];
  const active = rows.filter((row) => row.status === "active").length;
  const contested = rows.filter((row) => row.status === "contested").length;
  const critical = rows.filter((row) => row.criticality === "must_include").length;

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
