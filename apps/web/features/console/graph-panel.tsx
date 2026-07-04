"use client";

import { useQuery } from "@tanstack/react-query";
import { forceCollide } from "d3-force";
import { Maximize2, X } from "lucide-react";
import dynamic from "next/dynamic";
import { type ComponentType, useEffect, useMemo, useRef, useState } from "react";

import { getMemriseClient } from "@/lib/api";
import type { ConsoleEntry } from "@/lib/console";
import { LOCAL_INSPECTOR_SCOPE } from "@/lib/scope";

// Canvas + window based: never render on the server.
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
}) as ComponentType<Record<string, unknown>>;

type Turn = Extract<ConsoleEntry, { kind: "turn" }>;

type GraphNode = {
  id: string;
  label: string;
  color: string;
  critical?: boolean;
  // populated by the force engine / renderer
  x?: number;
  y?: number;
  __dims?: [number, number];
};

type GraphLink = {
  source: string;
  target: string;
  label: string;
  color: string;
};

type GraphData = { nodes: GraphNode[]; links: GraphLink[] };

// Minimal surface of the react-force-graph imperative handle that we use.
type D3ForceLike = {
  strength?: (v: number) => D3ForceLike;
  distance?: (v: number) => D3ForceLike;
};
type ForceGraphHandle = {
  zoomToFit: (ms?: number, padding?: number) => void;
  d3ReheatSimulation: () => void;
  d3Force: (name: string, force?: unknown) => D3ForceLike | undefined;
};

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

  const knowledgeGraph = useMemo<GraphData>(() => {
    const rawNodes = graph.data?.nodes ?? [];
    const nodes: GraphNode[] = rawNodes.map((node, index) => ({
      id: node.id,
      label: node.canonical_name,
      color: index === 0 ? "rgba(255,255,255,0.55)" : "rgba(255,255,255,0.22)",
    }));
    const links: GraphLink[] = (graph.data?.edges ?? []).map((edge) => ({
      source: edge.source_node_id,
      target: edge.target_node_id,
      label: edge.relation,
      color: "rgba(255,255,255,0.28)",
    }));
    return { nodes, links };
  }, [graph.data]);

  const memoryGraph = useMemo(() => buildMemoryRelationGraph(turn), [turn]);
  const showingKnowledgeGraph = knowledgeGraph.nodes.length > 0;
  const data = showingKnowledgeGraph ? knowledgeGraph : memoryGraph;
  const empty = data.nodes.length === 0;
  const resetKey = `${showingKnowledgeGraph ? "knowledge" : "memory"}-${turn?.id ?? "empty"}`;
  const [expanded, setExpanded] = useState(false);

  return (
    <section className="flex flex-1 flex-col overflow-hidden rounded-2xl border border-border bg-white/2">
      <div className="flex items-center justify-between gap-2 px-4 pt-4">
        <h2 className="font-mono text-[11px] uppercase tracking-widest text-faint">
          Knowledge graph
        </h2>
        <div className="flex items-center gap-3">
          {query ? <span className="font-mono text-xs text-white/40">{query}</span> : null}
          {!empty ? (
            <button
              type="button"
              onClick={() => setExpanded(true)}
              aria-label="Expand knowledge graph"
              className="rounded-md p-1 text-white/35 transition-colors hover:bg-white/10 hover:text-white"
            >
              <Maximize2 size={14} />
            </button>
          ) : null}
        </div>
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
        ) : (
          <ForceGraphCanvas data={data} resetKey={resetKey} />
        )}
      </div>

      {expanded ? (
        <GraphModal
          data={data}
          resetKey={`modal-${resetKey}`}
          query={query}
          onClose={() => setExpanded(false)}
        />
      ) : null}
    </section>
  );
}

/** Full-screen overlay showing the graph on a wide canvas. */
function GraphModal({
  data,
  resetKey,
  query,
  onClose,
}: {
  data: GraphData;
  resetKey: string;
  query: string | null;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm sm:p-8"
      onClick={onClose}
    >
      <div
        className="relative flex h-full w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-border bg-[#07080b] shadow-[0_24px_70px_-24px_rgba(0,0,0,0.9)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-2 border-b border-white/6 px-5 py-3">
          <div className="flex items-baseline gap-3">
            <h2 className="font-mono text-[11px] uppercase tracking-widest text-faint">
              Knowledge graph
            </h2>
            {query ? <span className="font-mono text-xs text-white/40">{query}</span> : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-md p-1.5 text-white/40 transition-colors hover:bg-white/10 hover:text-white"
          >
            <X size={16} />
          </button>
        </div>
        <div className="relative flex-1">
          <ForceGraphCanvas data={data} resetKey={resetKey} />
        </div>
      </div>
    </div>
  );
}

/** Force-directed canvas with monochrome pill nodes and animated relation edges. */
function ForceGraphCanvas({ data, resetKey }: { data: GraphData; resetKey: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<ForceGraphHandle | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize({ width, height });
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Spread pill-sized nodes apart: stronger repulsion, longer links, and a
  // collision force sized to each label so pills never overlap.
  useEffect(() => {
    const fg = graphRef.current;
    if (!fg || size.width === 0) return;
    fg.d3Force("charge")?.strength?.(-320);
    fg.d3Force("link")?.distance?.(110);
    fg.d3Force(
      "collide",
      forceCollide<GraphNode>((node) => node.label.length * 3.6 + 18).iterations(2),
    );
    fg.d3ReheatSimulation();
  }, [data, size.width]);

  return (
    <div ref={containerRef} className="absolute inset-0">
      {size.width > 0 ? (
        <ForceGraph2D
          key={resetKey}
          ref={graphRef}
          graphData={data}
          width={size.width}
          height={size.height}
          backgroundColor="rgba(0,0,0,0)"
          cooldownTicks={80}
          onEngineStop={() => graphRef.current?.zoomToFit(400, 36)}
          nodeRelSize={4}
          nodeColor={(node: GraphNode) => node.color}
          linkColor={(link: GraphLink) => link.color}
          linkWidth={1}
          linkDirectionalArrowLength={3}
          linkDirectionalArrowRelPos={1}
          linkDirectionalParticles={2}
          linkDirectionalParticleWidth={1.6}
          linkDirectionalParticleColor={() => "rgba(255,255,255,0.5)"}
          nodeCanvasObject={drawNode}
          nodePointerAreaPaint={paintNodeArea}
          linkCanvasObjectMode={() => "after"}
          linkCanvasObject={drawLinkLabel}
        />
      ) : null}
    </div>
  );
}

const FONT = "var(--font-jetbrains-mono), ui-monospace, monospace";

function drawNode(node: GraphNode, ctx: CanvasRenderingContext2D, scale: number) {
  const label = node.label;
  const fontSize = 12 / scale;
  ctx.font = `${fontSize}px ${FONT}`;
  const padX = 8 / scale;
  const padY = 5 / scale;
  const textWidth = ctx.measureText(label).width;
  const w = textWidth + padX * 2;
  const h = fontSize + padY * 2;
  const x = (node.x ?? 0) - w / 2;
  const y = (node.y ?? 0) - h / 2;

  ctx.beginPath();
  ctx.roundRect(x, y, w, h, h / 2);
  ctx.fillStyle = node.critical ? "rgba(245, 158, 11, 0.12)" : "rgba(255,255,255,0.05)";
  ctx.fill();
  ctx.lineWidth = 1 / scale;
  ctx.strokeStyle = node.color;
  ctx.stroke();

  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = "rgba(255,255,255,0.9)";
  ctx.fillText(label, node.x ?? 0, node.y ?? 0);

  node.__dims = [w, h];
}

function paintNodeArea(node: GraphNode, color: string, ctx: CanvasRenderingContext2D) {
  const [w, h] = node.__dims ?? [12, 12];
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.roundRect((node.x ?? 0) - w / 2, (node.y ?? 0) - h / 2, w, h, h / 2);
  ctx.fill();
}

type PositionedLink = { source: GraphNode; target: GraphNode; label: string };

function drawLinkLabel(link: PositionedLink, ctx: CanvasRenderingContext2D, scale: number) {
  if (!link.label) return;
  const { source, target } = link;
  if (source.x == null || target.x == null) return;
  const mx = (source.x + target.x!) / 2;
  const my = (source.y! + target.y!) / 2;
  const fontSize = 9 / scale;
  ctx.font = `${fontSize}px ${FONT}`;
  const textWidth = ctx.measureText(link.label).width;
  const padX = 4 / scale;
  const padY = 3 / scale;
  const w = textWidth + padX * 2;
  const h = fontSize + padY * 2;

  ctx.beginPath();
  ctx.roundRect(mx - w / 2, my - h / 2, w, h, 3 / scale);
  ctx.fillStyle = "rgba(8, 9, 12, 0.94)";
  ctx.fill();
  ctx.lineWidth = 0.75 / scale;
  ctx.strokeStyle = "rgba(255,255,255,0.12)";
  ctx.stroke();

  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = "rgba(255,255,255,0.5)";
  ctx.fillText(link.label, mx, my);
}

function buildMemoryRelationGraph(turn: Turn | null): GraphData {
  if (!turn || turn.recall.status !== "done") {
    return { nodes: [], links: [] };
  }
  const rows = turn.recall.rows ?? [];
  if (rows.length === 0) {
    return { nodes: [], links: [] };
  }

  const nodeMap = new Map<string, GraphNode>();
  const linkKeys = new Set<string>();
  const links: GraphLink[] = [];

  rows.slice(0, 8).forEach((row) => {
    const triple = memoryToTriple(row.memory);
    const sourceId = stableNodeId("source", triple.source);
    const targetId = stableNodeId("target", triple.target);

    if (!nodeMap.has(sourceId)) {
      nodeMap.set(sourceId, {
        id: sourceId,
        label: truncate(triple.source, 28),
        color: row.critical ? "rgba(252, 211, 77, 0.6)" : "rgba(255,255,255,0.28)",
        critical: row.critical,
      });
    }
    if (!nodeMap.has(targetId)) {
      nodeMap.set(targetId, {
        id: targetId,
        label: truncate(triple.target, 32),
        color: targetBorderColor(triple.targetType),
      });
    }

    const linkKey = `${sourceId}:${triple.relation}:${targetId}`;
    if (linkKeys.has(linkKey)) return;
    linkKeys.add(linkKey);

    links.push({
      source: sourceId,
      target: targetId,
      label: triple.relation,
      color: row.critical ? "rgba(245, 158, 11, 0.55)" : "rgba(110, 231, 183, 0.4)",
    });
  });

  return { nodes: [...nodeMap.values()], links };
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

function targetBorderColor(targetType: string): string {
  if (targetType === "Technology") return "rgba(110, 231, 183, 0.5)";
  if (targetType === "Action") return "rgba(248, 113, 113, 0.45)";
  if (targetType === "Person") return "rgba(125, 211, 252, 0.5)";
  return "rgba(255,255,255,0.24)";
}

function truncate(value: string, max: number): string {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}
