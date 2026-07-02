"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { components } from "memrise-memory-sdk";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils/cn";
import { getMemriseClient } from "@/lib/api";
import { LOCAL_INSPECTOR_SCOPE } from "@/lib/scope";

type RetrievalTraceSummary = components["schemas"]["RetrievalTraceSummary"];
type RetrievalItemSummary = components["schemas"]["RetrievalItemSummary"];

export function RetrievalsPanel() {
  const client = getMemriseClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const traces = useQuery({
    queryKey: ["retrievals", "local"],
    queryFn: () =>
      client.listRetrievals({
        namespaceId: LOCAL_INSPECTOR_SCOPE.namespaceId,
        limit: 20,
      }),
    retry: false,
  });
  const detail = useQuery({
    queryKey: ["retrieval", selectedId],
    queryFn: () => client.getRetrieval(selectedId!),
    enabled: selectedId !== null,
    retry: false,
  });

  return (
    <div>
      <PageHeader
        eyebrow="Explainability"
        title="Retrievals"
        description="Every retrieval leaves a trace. Inspect the ranking signals that decided what made it into context."
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)]">
        <Card>
          <CardTitle>Retrieval Traces</CardTitle>
          {traces.isError ? (
            <p className="mt-3 text-sm text-danger">{traces.error.message}</p>
          ) : null}
          <div className="mt-4 space-y-1.5">
            {(traces.data ?? []).map((trace: RetrievalTraceSummary) => {
              const selected = selectedId === trace.id;
              return (
                <button
                  key={trace.id}
                  type="button"
                  onClick={() => setSelectedId(trace.id)}
                  className={cn(
                    "block w-full rounded-xl border px-3.5 py-3 text-left transition-all duration-200",
                    selected
                      ? "border-white/40 bg-white/6"
                      : "border-border bg-white/2 hover:border-white/20 hover:bg-white/4",
                  )}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <strong className="text-sm">{trace.query}</strong>
                    {trace.task_type ? <Badge>{trace.task_type}</Badge> : null}
                    {trace.project_id ? <Badge>{trace.project_id}</Badge> : null}
                  </div>
                  <p className="mt-1.5 font-mono text-[11px] text-faint">
                    {new Date(trace.created_at).toLocaleString()} · budget {trace.token_budget}
                  </p>
                </button>
              );
            })}
            {traces.data?.length === 0 ? (
              <p className="py-10 text-center text-sm text-muted">
                No retrieval traces yet. Run a retrieval in the playground or via the API.
              </p>
            ) : null}
          </div>
        </Card>

        <Card>
          <CardTitle>Ranking Signals</CardTitle>
          {!selectedId ? (
            <p className="mt-3 text-sm text-muted">
              Select a retrieval trace to inspect its items.
            </p>
          ) : detail.isError ? (
            <p className="mt-3 text-sm text-danger">{detail.error.message}</p>
          ) : detail.isLoading ? (
            <p className="mt-3 text-sm text-muted">Loading trace items…</p>
          ) : (
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full border-separate border-spacing-0 text-left text-sm">
                <thead>
                  <tr className="font-mono text-[11px] uppercase tracking-wider text-faint">
                    <th className="pb-2 pr-3 font-medium">Rank</th>
                    <th className="pb-2 pr-3 font-medium">Source</th>
                    <th className="pb-2 pr-3 font-medium">Ctx</th>
                    <th className="pb-2 pr-3 font-medium">Lexical</th>
                    <th className="pb-2 pr-3 font-medium">Graph</th>
                    <th className="pb-2 pr-3 font-medium">Useful</th>
                  </tr>
                </thead>
                <tbody>
                  {(detail.data?.items ?? []).map((item: RetrievalItemSummary) => (
                    <tr
                      key={`${item.retrieval_id}-${item.memory_version_id}-${item.final_rank}`}
                      className="border-t border-border transition-colors hover:bg-white/3"
                    >
                      <td className="border-t border-border py-2.5 pr-3 font-mono text-muted">
                        #{item.final_rank}
                      </td>
                      <td className="border-t border-border py-2.5 pr-3">
                        <Badge>{item.source_type}</Badge>
                      </td>
                      <td className="border-t border-border py-2.5 pr-3">
                        {item.selected_for_context ? (
                          <Badge variant="ok">in</Badge>
                        ) : (
                          <span className="font-mono text-xs text-faint">—</span>
                        )}
                      </td>
                      <Score value={item.lexical_score} />
                      <Score value={item.graph_score} />
                      <Score value={item.usefulness_score} />
                    </tr>
                  ))}
                </tbody>
              </table>
              {(detail.data?.items ?? []).length === 0 ? (
                <p className="py-10 text-center text-sm text-muted">No retrieval items recorded.</p>
              ) : null}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

function Score({ value }: { value: number | null | undefined }) {
  const has = value !== null && value !== undefined;
  const pct = has ? Math.max(0, Math.min(1, value)) : 0;
  return (
    <td className="border-t border-border py-2.5 pr-3">
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs tabular-nums text-foreground">
          {has ? value.toFixed(2) : "—"}
        </span>
        <span className="hidden h-1 w-10 overflow-hidden rounded-full bg-white/6 sm:block">
          <span
            className="block h-full rounded-full"
            style={{ width: `${pct * 100}%`, background: "rgba(255,255,255,0.7)" }}
          />
        </span>
      </div>
    </td>
  );
}
