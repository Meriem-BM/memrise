"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { components } from "memrise-memory-sdk";

import { Badge } from "@/components/ui/badge";
import { Card, CardTitle } from "@/components/ui/card";
import { getMemriseClient } from "@/lib/api";
import { LOCAL_INSPECTOR_SCOPE } from "@/lib/scope";

type RetrievalTraceSummary = components["schemas"]["RetrievalTraceSummary"];
type RetrievalDetail = components["schemas"]["RetrievalDetail"];
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
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <Card>
        <CardTitle>Retrieval Traces</CardTitle>
        {traces.isError ? (
          <p className="mt-3 text-sm text-red-600">{traces.error.message}</p>
        ) : null}
        <div className="mt-4 divide-y divide-slate-200">
          {(traces.data ?? []).map((trace: RetrievalTraceSummary) => (
            <button
              key={trace.id}
              type="button"
              onClick={() => setSelectedId(trace.id)}
              className={`block w-full py-3 text-left ${
                selectedId === trace.id ? "bg-slate-50" : ""
              }`}
            >
              <div className="flex flex-wrap items-center gap-2">
                <strong className="text-sm">{trace.query}</strong>
                {trace.task_type ? <Badge>{trace.task_type}</Badge> : null}
                {trace.project_id ? <Badge>{trace.project_id}</Badge> : null}
              </div>
              <p className="mt-1 text-xs text-slate-500">
                {new Date(trace.created_at).toLocaleString()} · budget {trace.token_budget}
              </p>
            </button>
          ))}
          {traces.data?.length === 0 ? (
            <p className="py-8 text-sm text-slate-500">
              No retrieval traces yet. Run a retrieval in the playground or via the API.
            </p>
          ) : null}
        </div>
      </Card>
      <Card>
        <CardTitle>Ranking Signals</CardTitle>
        {!selectedId ? (
          <p className="mt-3 text-sm text-slate-500">Select a retrieval trace to inspect items.</p>
        ) : detail.isError ? (
          <p className="mt-3 text-sm text-red-600">{detail.error.message}</p>
        ) : detail.isLoading ? (
          <p className="mt-3 text-sm text-slate-500">Loading trace items…</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-xs uppercase text-slate-500">
                <tr>
                  <th className="py-2 pr-3">Rank</th>
                  <th className="py-2 pr-3">Source</th>
                  <th className="py-2 pr-3">Selected</th>
                  <th className="py-2 pr-3">Lexical</th>
                  <th className="py-2 pr-3">Graph</th>
                  <th className="py-2 pr-3">Usefulness</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(detail.data?.items ?? []).map((item: RetrievalItemSummary) => (
                  <tr key={`${item.retrieval_id}-${item.memory_version_id}-${item.final_rank}`}>
                    <td className="py-2 pr-3">{item.final_rank}</td>
                    <td className="py-2 pr-3">
                      <Badge>{item.source_type}</Badge>
                    </td>
                    <td className="py-2 pr-3">{item.selected_for_context ? "yes" : "no"}</td>
                    <td className="py-2 pr-3">{formatScore(item.lexical_score)}</td>
                    <td className="py-2 pr-3">{formatScore(item.graph_score)}</td>
                    <td className="py-2 pr-3">{formatScore(item.usefulness_score)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(detail.data?.items ?? []).length === 0 ? (
              <p className="py-8 text-sm text-slate-500">No retrieval items recorded.</p>
            ) : null}
          </div>
        )}
      </Card>
    </div>
  );
}

function formatScore(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  return value.toFixed(2);
}
