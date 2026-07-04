"use client";

import "@xyflow/react/dist/style.css";

import { Background, BackgroundVariant, ReactFlow } from "@xyflow/react";
import { useQuery } from "@tanstack/react-query";

import { getMemriseClient } from "@/lib/api";
import { LOCAL_INSPECTOR_SCOPE } from "@/lib/scope";

export function GraphPanel({
  graphQuery,
}: {
  graphQuery: { query: string; nonce: number } | null;
}) {
  const client = getMemriseClient();
  const query = graphQuery?.query ?? null;
  const graph = useQuery({
    queryKey: ["graph", graphQuery?.query, graphQuery?.nonce],
    enabled: graphQuery !== null,
    retry: false,
    queryFn: () =>
      client.graphNeighborhood({
        namespaceId: LOCAL_INSPECTOR_SCOPE.namespaceId,
        agentId: LOCAL_INSPECTOR_SCOPE.agentId,
        projectId: LOCAL_INSPECTOR_SCOPE.projectId,
        query: (graphQuery as { query: string; nonce: number }).query,
        hops: 1,
      }),
  });

  const rawNodes = graph.data?.nodes ?? [];
  const nodes = rawNodes.map((node, index) => {
    const angle = (2 * Math.PI * index) / Math.max(rawNodes.length, 1);
    const radius = index === 0 ? 0 : 150;
    return {
      id: node.id,
      position: { x: 220 + radius * Math.cos(angle), y: 160 + radius * Math.sin(angle) },
      data: { label: node.canonical_name },
      style: {
        background: "#000",
        color: "#fff",
        border: "1px solid rgba(255,255,255,0.25)",
        borderRadius: 999,
        fontSize: 11,
        fontFamily: "var(--font-jetbrains-mono)",
      },
    };
  });
  const edges = (graph.data?.edges ?? []).map((edge) => ({
    id: edge.id,
    source: edge.source_node_id,
    target: edge.target_node_id,
    label: edge.relation,
    animated: true,
    labelStyle: { fill: "rgba(255,255,255,0.5)", fontSize: 9 },
    style: { stroke: "rgba(255,255,255,0.3)" },
  }));

  return (
    <section className="flex flex-1 flex-col overflow-hidden rounded-2xl border border-border bg-white/2">
      <div className="flex items-center justify-between px-4 pt-4">
        <h2 className="font-mono text-[11px] uppercase tracking-widest text-faint">
          Knowledge graph
        </h2>
        {query ? <span className="font-mono text-xs text-white/40">{query}</span> : null}
      </div>
      {graph.isError ? (
        <p className="px-4 pt-3 text-sm text-danger">{graph.error.message}</p>
      ) : null}
      {query === null ? (
        <p className="px-4 pt-3 text-sm text-muted">Grows as the agent learns.</p>
      ) : null}
      <div className="min-h-56 flex-1 p-2">
        <ReactFlow nodes={nodes} edges={edges} fitView proOptions={{ hideAttribution: true }}>
          <Background
            variant={BackgroundVariant.Dots}
            gap={22}
            size={1}
            color="rgba(255,255,255,0.06)"
          />
        </ReactFlow>
      </div>
    </section>
  );
}
