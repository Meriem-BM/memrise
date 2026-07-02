"use client";

import "@xyflow/react/dist/style.css";

import { Background, Controls, ReactFlow } from "@xyflow/react";
import { useQuery } from "@tanstack/react-query";

import { Card, CardTitle } from "@/components/ui/card";
import { getMemriseClient } from "@/lib/api";
import { LOCAL_INSPECTOR_SCOPE } from "@/lib/scope";

export function GraphPanel() {
  const client = getMemriseClient();
  const graph = useQuery({
    queryKey: ["graph", "atlas"],
    queryFn: () =>
      client.graphNeighborhood({
        namespaceId: LOCAL_INSPECTOR_SCOPE.namespaceId,
        agentId: LOCAL_INSPECTOR_SCOPE.agentId,
        projectId: LOCAL_INSPECTOR_SCOPE.projectId,
        query: "Atlas",
        hops: 1,
      }),
    retry: false,
  });
  const nodes = (graph.data?.nodes ?? []).map((node, index) => ({
    id: node.id,
    position: { x: index * 180, y: index % 2 === 0 ? 40 : 160 },
    data: { label: node.canonical_name },
  }));
  const edges = (graph.data?.edges ?? []).map((edge) => ({
    id: edge.id,
    source: edge.source_node_id,
    target: edge.target_node_id,
    label: edge.relation,
  }));
  return (
    <Card className="h-[640px]">
      <CardTitle>Graph Neighborhood</CardTitle>
      <div className="mt-4 h-[560px] overflow-hidden rounded border border-slate-200">
        <ReactFlow nodes={nodes} edges={edges} fitView>
          <Background />
          <Controls />
        </ReactFlow>
      </div>
    </Card>
  );
}
