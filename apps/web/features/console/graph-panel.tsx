"use client";

import "@xyflow/react/dist/style.css";

import { Background, BackgroundVariant, ReactFlow } from "@xyflow/react";
import type { Edge, Node } from "@xyflow/react";
import { useQuery } from "@tanstack/react-query";

import { getMemriseClient } from "@/lib/api";
import type { ConsoleEntry } from "@/lib/console";
import { LOCAL_INSPECTOR_SCOPE } from "@/lib/scope";

type Turn = Extract<ConsoleEntry, { kind: "turn" }>;

export function GraphPanel({
  graphQuery,
  turn,
}: {
  graphQuery: { query: string; nonce: number } | null;
  turn: Turn | null;
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
  const graphNodes: Node[] = rawNodes.map((node, index) => {
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
  const graphEdges: Edge[] = (graph.data?.edges ?? []).map((edge) => ({
    id: edge.id,
    source: edge.source_node_id,
    target: edge.target_node_id,
    label: edge.relation,
    animated: true,
    ...relationLabelStyles(),
    style: { stroke: "rgba(255,255,255,0.3)" },
  }));
  const memoryGraph = buildMemoryRelationGraph(turn);
  const showingKnowledgeGraph = graphNodes.length > 0;
  const nodes = showingKnowledgeGraph ? graphNodes : memoryGraph.nodes;
  const edges = showingKnowledgeGraph ? graphEdges : memoryGraph.edges;
  const empty = nodes.length === 0;

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
      ) : !showingKnowledgeGraph && !empty ? (
        <p className="px-4 pt-3 text-xs text-faint">
          Showing memory-derived relations while the projected knowledge graph is empty.
        </p>
      ) : null}
      <div className="relative min-h-56 flex-1 p-2">
        {empty ? (
          <p className="absolute inset-x-4 top-12 z-10 text-sm text-muted">
            No graph data for this turn yet.
          </p>
        ) : null}
        <ReactFlow
          key={`${showingKnowledgeGraph ? "knowledge" : "memory"}-${turn?.id ?? "empty"}-${nodes.length}`}
          nodes={nodes}
          edges={edges}
          fitView
          fitViewOptions={{ padding: 0.22 }}
          proOptions={{ hideAttribution: true }}
        >
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

function buildMemoryRelationGraph(turn: Turn | null): { nodes: Node[]; edges: Edge[] } {
  if (!turn || turn.recall.status !== "done") {
    return { nodes: [], edges: [] };
  }
  const rows = turn.recall.rows ?? [];
  if (rows.length === 0) {
    return { nodes: [], edges: [] };
  }

  const nodeMap = new Map<string, Node>();
  const edgeKeys = new Set<string>();
  const edges: Edge[] = [];

  rows.slice(0, 8).forEach((row, index) => {
    const triple = memoryToTriple(row.memory);
    const sourceId = stableNodeId("source", triple.source);
    const targetId = stableNodeId("target", triple.target);
    const y = (index % 5) * 92;
    const xOffset = Math.floor(index / 5) * 430;

    if (!nodeMap.has(sourceId)) {
      nodeMap.set(sourceId, {
        id: sourceId,
        position: { x: xOffset, y },
        data: { label: `${triple.sourceType}\n${truncate(triple.source, 42)}` },
        style: nodeStyle(
          row.critical ? "rgba(252, 211, 77, 0.5)" : "rgba(255,255,255,0.24)",
          "#050505",
        ),
      });
    }

    if (!nodeMap.has(targetId)) {
      nodeMap.set(targetId, {
        id: targetId,
        position: { x: xOffset + 310, y },
        data: { label: `${triple.targetType}\n${truncate(triple.target, 48)}` },
        style: nodeStyle(targetBorderColor(triple.targetType), "#020202"),
      });
    }

    const edgeKey = `${sourceId}:${triple.relation}:${targetId}`;
    if (edgeKeys.has(edgeKey)) {
      return;
    }
    edgeKeys.add(edgeKey);

    edges.push({
      id: `memory-edge-${row.memory.memory_version_id}`,
      source: sourceId,
      target: targetId,
      label: triple.relation,
      animated: true,
      ...relationLabelStyles(),
      style: {
        stroke: row.critical ? "rgba(245, 158, 11, 0.62)" : "rgba(110, 231, 183, 0.42)",
      },
      data: { memoryVersionId: row.memory.memory_version_id },
    });
  });

  return { nodes: [...nodeMap.values()], edges };
}

type MemoryLike = NonNullable<Turn["recall"]["rows"]>[number]["memory"];

type MemoryTriple = {
  source: string;
  sourceType: string;
  relation: string;
  target: string;
  targetType: string;
};

function memoryToTriple(memory: MemoryLike): MemoryTriple {
  const content = memory.content;
  const lowerContent = content.toLowerCase();
  const subject = normalizeSubject(memory.subject);
  const key = memory.key.toLowerCase();

  const name = extractName(content);
  if (name || key.includes("user_name")) {
    return {
      source: "User",
      sourceType: "Person",
      relation: "HAS_NAME",
      target: name ?? subject,
      targetType: "Person",
    };
  }

  if (lowerContent.includes("lockfile") || key.includes("lockfile")) {
    return {
      source: subject,
      sourceType: "Component",
      relation: "PROHIBITS",
      target: "manual lockfile edits",
      targetType: "Action",
    };
  }

  const packageManager = extractPackageManager(content);
  if (packageManager || key.includes("package_manager")) {
    return {
      source: subject,
      sourceType: "Project",
      relation: "USES",
      target: packageManager ?? "package manager",
      targetType: "Technology",
    };
  }

  return {
    source: subject,
    sourceType: humanize(memory.type),
    relation: relationFromKey(memory.key),
    target: content,
    targetType: memory.criticality === "must_include" ? "Constraint" : "Memory",
  };
}

function normalizeSubject(value: string): string {
  return value.replaceAll("_", " ").replaceAll("-", " ").replace(/\s+/g, " ").trim();
}

function extractName(content: string): string | null {
  const match =
    content.match(/\bname\s+(?:is|as)\s+([A-Z][\p{L}\p{N}_-]*)/u) ??
    content.match(/\bcalled\s+([A-Z][\p{L}\p{N}_-]*)/u);
  return match?.[1] ?? null;
}

function extractPackageManager(content: string): string | null {
  if (/\bpnpm\b/i.test(content)) return "pnpm";
  if (/\bnpm\b/i.test(content)) return "npm";
  if (/\byarn\b/i.test(content)) return "yarn";
  if (/\bbun\b/i.test(content)) return "bun";
  return null;
}

function relationFromKey(key: string): string {
  return (
    key
      .replace(/[^a-zA-Z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .toUpperCase() || "RELATES_TO"
  );
}

function humanize(value: string): string {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(" ");
}

function stableNodeId(prefix: string, label: string): string {
  const slug = label
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return `${prefix}-${slug || "node"}`;
}

function nodeStyle(borderColor: string, background: string): Node["style"] {
  return {
    background,
    color: "#fff",
    border: `1px solid ${borderColor}`,
    borderRadius: 999,
    fontSize: 10,
    fontFamily: "var(--font-jetbrains-mono)",
    lineHeight: 1.3,
    padding: 10,
    width: 165,
    minHeight: 54,
    textAlign: "center",
    whiteSpace: "pre-wrap",
  };
}

function targetBorderColor(targetType: string): string {
  if (targetType === "Technology") return "rgba(110, 231, 183, 0.5)";
  if (targetType === "Action") return "rgba(248, 113, 113, 0.42)";
  if (targetType === "Person") return "rgba(125, 211, 252, 0.45)";
  return "rgba(255,255,255,0.2)";
}

function relationLabelStyles(): Pick<
  Edge,
  "labelBgBorderRadius" | "labelBgPadding" | "labelBgStyle" | "labelStyle"
> {
  return {
    labelBgBorderRadius: 4,
    labelBgPadding: [8, 4],
    labelBgStyle: {
      fill: "rgba(5, 5, 5, 0.96)",
      stroke: "rgba(255,255,255,0.18)",
      strokeWidth: 1,
    },
    labelStyle: {
      fill: "rgba(255,255,255,0.92)",
      fontFamily: "var(--font-jetbrains-mono)",
      fontSize: 10,
      fontWeight: 700,
    },
  };
}

function truncate(value: string, max: number): string {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}
