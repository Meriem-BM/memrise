"use client";

import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Badge, statusVariant } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getMemriseClient } from "@/lib/api";
import { LOCAL_INSPECTOR_SCOPE } from "@/lib/scope";
import type { MemorySummary } from "@/types/memory";

export function MemoriesPanel() {
  const client = getMemriseClient();
  const [filter, setFilter] = useState("");
  const memories = useQuery({
    queryKey: ["memories", "list"],
    queryFn: () =>
      client.listMemories({
        namespaceId: LOCAL_INSPECTOR_SCOPE.namespaceId,
        agentId: LOCAL_INSPECTOR_SCOPE.agentId,
        projectId: LOCAL_INSPECTOR_SCOPE.projectId,
      }),
    retry: false,
  });

  const rows = useMemo(() => memories.data ?? [], [memories.data]);
  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((m: MemorySummary) =>
      [m.subject, m.content, m.type, m.status].some((v) =>
        String(v ?? "")
          .toLowerCase()
          .includes(q),
      ),
    );
  }, [rows, filter]);

  return (
    <div>
      <PageHeader
        eyebrow="Canonical Store"
        title="Memories"
        description="Everything Memrise has distilled into durable, canonical knowledge."
        actions={
          <div className="relative">
            <Search
              size={15}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint"
            />
            <Input
              className="w-64 pl-9"
              placeholder="Filter memories…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </div>
        }
      />

      <div className="grid gap-3">
        {filtered.map((memory: MemorySummary, i: number) => (
          <Link
            key={memory.memory_id}
            href={`/memories/${memory.memory_id}`}
            className="animate-rise block"
            style={{ animationDelay: `${Math.min(i, 12) * 35}ms` }}
          >
            <Card interactive className="p-4">
              <div className="flex flex-wrap items-center gap-2">
                <strong className="text-[15px] font-medium tracking-tight">{memory.subject}</strong>
                <Badge>{memory.type}</Badge>
                <Badge variant={statusVariant(memory.status)}>{memory.status}</Badge>
                <Badge variant={statusVariant(memory.criticality)}>{memory.criticality}</Badge>
              </div>
              <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-muted">
                {memory.content}
              </p>
            </Card>
          </Link>
        ))}

        {rows.length > 0 && filtered.length === 0 ? (
          <Card className="py-10 text-center text-sm text-muted">
            No memories match “{filter}”.
          </Card>
        ) : null}

        {memories.isSuccess && rows.length === 0 ? (
          <Card className="py-14 text-center">
            <p className="text-sm text-muted">No memories yet.</p>
            <p className="mt-1 text-xs text-faint">
              Capture something in the playground to seed the store.
            </p>
          </Card>
        ) : null}

        {memories.isError ? (
          <Card className="border-danger/30 py-6 text-center text-sm text-danger">
            {memories.error.message}
          </Card>
        ) : null}
      </div>
    </div>
  );
}
