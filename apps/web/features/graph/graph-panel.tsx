"use client";

import "@xyflow/react/dist/style.css";

import { Background, BackgroundVariant, Controls, ReactFlow } from "@xyflow/react";
import { useQuery } from "@tanstack/react-query";

import { PageHeader } from "@/components/page-header";
import { Card } from "@/components/ui/card";
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
    position: { x: index * 200, y: index % 2 === 0 ? 40 : 200 },
    data: { label: node.canonical_name },
  }));
  const edges = (graph.data?.edges ?? []).map((edge) => ({
    id: edge.id,
    source: edge.source_node_id,
    target: edge.target_node_id,
    label: edge.relation,
    animated: true,
  }));

  return (
    <div>
      <PageHeader
        eyebrow="Knowledge Graph"
        title="Graph Neighborhood"
        description="How memories connect. Explore the entities and relations surrounding the current focus."
      />

      <Card className="h-[640px] p-3">
        <div className="h-full overflow-hidden rounded-xl border border-border">
          <ReactFlow nodes={nodes} edges={edges} fitView proOptions={{ hideAttribution: true }}>
            <Background
              variant={BackgroundVariant.Dots}
              gap={22}
              size={1}
              color="rgba(255,255,255,0.08)"
            />
            <Controls />
          </ReactFlow>
        </div>
      </Card>
    </div>
  );
}
