"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, Database, History, ShieldAlert, Zap } from "lucide-react";
import Link from "next/link";
import type { components } from "memrise-memory-sdk";

import { PageHeader } from "@/components/page-header";
import { Badge, statusVariant } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { getMemriseClient } from "@/lib/api";
import { formatCount } from "@/lib/utils/format";
import { LOCAL_INSPECTOR_SCOPE } from "@/lib/scope";
import { useCountUp } from "@/hooks/useCountUp";

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
  const total = rows.length;
  const active = rows.filter((row: MemorySummary) => row.status === "active").length;
  const contested = rows.filter((row: MemorySummary) => row.status === "contested").length;
  const critical = rows.filter((row: MemorySummary) => row.criticality === "must_include").length;

  const online = health.data?.status === "ok";

  return (
    <div>
      <PageHeader
        eyebrow="Inspector"
        title="Living memory, at a glance"
        description="A real-time window into what Memrise remembers — backend health, the shape of the canonical store, and the traces behind every retrieval."
        actions={
          <Link href="/playground">
            <Button>
              <Zap size={15} />
              Open Playground
            </Button>
          </Link>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Service */}
        <Card interactive className="animate-rise" style={{ animationDelay: "40ms" }}>
          <div className="flex items-center gap-2 text-muted">
            <Activity size={16} />
            <CardTitle>Service</CardTitle>
          </div>
          <div className="mt-5 flex items-center gap-3">
            <span
              className={online ? "pulse-dot" : ""}
              style={{
                display: "inline-block",
                height: 12,
                width: 12,
                borderRadius: 9999,
                background: health.isError ? "var(--danger)" : online ? "var(--ok)" : "var(--warn)",
              }}
            />
            <p className="text-3xl font-medium capitalize tracking-tight">
              {health.data?.status ?? (health.isError ? "offline" : "unknown")}
            </p>
          </div>
          <Badge variant={statusVariant(health.data?.database)} className="mt-4">
            db · {health.data?.database ?? "not checked"}
          </Badge>
        </Card>

        {/* Memories */}
        <Card interactive className="animate-rise" style={{ animationDelay: "100ms" }}>
          <div className="flex items-center gap-2 text-muted">
            <Database size={16} />
            <CardTitle>Memories</CardTitle>
          </div>
          <div className="mt-5 flex items-baseline gap-2">
            <AnimatedNumber value={total} className="text-4xl font-medium tracking-tight" />
            <span className="text-sm text-muted">total</span>
          </div>
          <dl className="mt-5 grid grid-cols-3 gap-3">
            <Metric label="active" value={active} tone="#ffffff" />
            <Metric label="critical" value={critical} tone="var(--ok)" />
            <Metric label="contested" value={contested} tone="var(--warn)" />
          </dl>
        </Card>

        {/* Recent retrievals */}
        <Card interactive className="animate-rise" style={{ animationDelay: "160ms" }}>
          <div className="flex items-center gap-2 text-muted">
            <History size={16} />
            <CardTitle>Recent Retrievals</CardTitle>
          </div>
          <p className="mt-5 text-sm leading-relaxed text-muted">
            Retrieval traces appear here once the playground or API returns memory context.
          </p>
          <Link
            href="/retrievals"
            className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-white/70 transition-colors hover:text-white"
          >
            View ranking signals →
          </Link>
        </Card>
      </div>

      {memories.isError ? (
        <Card className="mt-4 flex items-center gap-3 border-danger/30">
          <ShieldAlert size={18} className="text-danger" />
          <p className="text-sm text-danger">{memories.error.message}</p>
        </Card>
      ) : null}
    </div>
  );
}

function AnimatedNumber({ value, className }: { value: number; className?: string }) {
  const display = useCountUp(value);
  return <span className={className}>{formatCount(display)}</span>;
}

function Metric({ label, value, tone }: { label: string; value: number; tone: string }) {
  const display = useCountUp(value);
  return (
    <div>
      <dt className="font-mono text-[11px] uppercase tracking-wider text-faint">{label}</dt>
      <dd className="mt-0.5 text-2xl font-medium tracking-tight" style={{ color: tone }}>
        {formatCount(display)}
      </dd>
    </div>
  );
}
