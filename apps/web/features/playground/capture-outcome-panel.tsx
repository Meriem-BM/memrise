import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";

export type CaptureMemory = {
  memory_id: string;
  subject: string;
  key: string;
  content: string;
  status: string;
  type: string;
};

export type CaptureJob = {
  id: string;
  type: string;
  status: string;
  last_error: string | null;
};

export type CaptureOutcome = {
  episodeIds: string[];
  jobs: CaptureJob[];
  memories: CaptureMemory[];
  skippedExtraction: boolean;
};

export function CaptureOutcomePanel({ outcome }: { outcome: CaptureOutcome }) {
  const extractionFailed = outcome.jobs.some((job) => job.status === "failed");
  const extractionDone = outcome.jobs.every(
    (job) => job.status === "completed" || job.status === "failed",
  );

  return (
    <div className="mt-4 space-y-4 rounded border border-slate-200 bg-slate-50 p-4 text-sm">
      <OutcomeStep
        done
        label={`Episode saved (${outcome.episodeIds.length})`}
        detail={outcome.episodeIds[0]}
      />

      {outcome.skippedExtraction ? (
        <OutcomeStep
          done
          label="Extraction skipped"
          detail="Episode stored, but content did not pass the importance gate."
        />
      ) : (
        <>
          {outcome.jobs.map((job) => (
            <OutcomeStep
              key={job.id}
              done={job.status === "completed"}
              failed={job.status === "failed"}
              label={`${formatJobType(job.type)} · ${job.status}`}
              detail={job.last_error ?? job.id}
            />
          ))}

          {extractionDone && !extractionFailed && outcome.memories.length > 0 ? (
            <div className="space-y-2">
              <p className="font-medium text-slate-800">Memories created</p>
              {outcome.memories.map((memory) => (
                <Link
                  key={memory.memory_id}
                  href={`/memories/${memory.memory_id}`}
                  className="block rounded border border-white bg-white px-3 py-2 hover:border-slate-300"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{memory.subject}</span>
                    <Badge>{memory.type}</Badge>
                    <Badge>{memory.status}</Badge>
                  </div>
                  <p className="mt-1 text-xs text-slate-600">{memory.content}</p>
                </Link>
              ))}
            </div>
          ) : null}

          {extractionDone && !extractionFailed && outcome.memories.length === 0 ? (
            <OutcomeStep
              done
              label="No new memories"
              detail="Extraction finished but nothing was accepted into the canonical store."
            />
          ) : null}
        </>
      )}
    </div>
  );
}

function OutcomeStep({
  label,
  detail,
  done = false,
  failed = false,
}: {
  label: string;
  detail?: string;
  done?: boolean;
  failed?: boolean;
}) {
  const Icon = failed ? XCircle : done ? CheckCircle2 : Loader2;
  const iconClass = failed
    ? "text-red-600"
    : done
      ? "text-emerald-600"
      : "animate-spin text-slate-400";

  return (
    <div className="flex gap-2">
      <Icon className={`mt-0.5 shrink-0 ${iconClass}`} size={16} />
      <div className="min-w-0">
        <p className="font-medium text-slate-800">{label}</p>
        {detail ? <p className="truncate text-xs text-slate-500">{detail}</p> : null}
      </div>
    </div>
  );
}

function formatJobType(type: string): string {
  return type.replaceAll("_", " ");
}
