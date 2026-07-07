"use client";

import { CheckCircle2, ChevronDown, Circle, Loader2, XCircle } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ErrorNote } from "@/components/trace/error-note";
import { ReasonBadge } from "@/components/trace/reason-badge";
import { ScoreBar } from "@/components/trace/score-bar";
import type { TraceStep } from "@/lib/trace";
import { cn } from "@/lib/utils/cn";

const icons = {
  ok: { Icon: CheckCircle2, className: "text-ok" },
  rejected: { Icon: XCircle, className: "text-warn" },
  failed: { Icon: XCircle, className: "text-danger" },
  pending: { Icon: Loader2, className: "animate-spin text-muted" },
  info: { Icon: Circle, className: "text-muted" },
} as const;

export function PipelineTrace({ steps }: { steps: TraceStep[] }) {
  return (
    <ol className="space-y-2">
      {steps.map((step) => (
        <TraceRow key={step.id} step={step} />
      ))}
    </ol>
  );
}

function TraceRow({ step }: { step: TraceStep }) {
  const [open, setOpen] = useState(false);
  const { Icon, className } = icons[step.decision];

  return (
    <li className="rounded-lg border border-border bg-white/2 px-3 py-2 text-sm">
      <div className="flex items-center gap-2">
        <Icon size={15} className={cn("shrink-0", className)} />
        {step.href ? (
          <Link href={step.href} className="font-medium hover:underline">
            {step.label}
          </Link>
        ) : (
          <span className="font-medium">{step.label}</span>
        )}
        {step.reasonCode ? <ReasonBadge code={step.reasonCode} /> : null}
        {step.detail !== undefined ? (
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            className="ml-auto text-faint transition-colors hover:text-white"
            aria-label="Toggle details"
          >
            <ChevronDown size={14} className={cn("transition-transform", open && "rotate-180")} />
          </button>
        ) : null}
      </div>
      {step.error ? <ErrorNote className="mt-2" message={step.error} /> : null}
      {step.score !== undefined ? (
        <div className="mt-2">
          <ScoreBar label="promotion" value={step.score} />
        </div>
      ) : null}
      {open ? (
        <pre className="mt-2 overflow-auto rounded-md border border-border bg-black p-2 font-mono text-xs leading-relaxed text-muted">
          {JSON.stringify(step.detail, null, 2)}
        </pre>
      ) : null}
    </li>
  );
}
