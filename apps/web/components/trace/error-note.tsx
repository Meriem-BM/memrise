import { AlertTriangle } from "lucide-react";

import { cn } from "@/lib/utils/cn";

export function ErrorNote({ message, className }: { message: string; className?: string }) {
  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-2 rounded-lg border border-danger/25 bg-danger/8 px-3 py-2",
        className,
      )}
    >
      <AlertTriangle size={14} className="mt-0.5 shrink-0 text-danger" />
      <p className="wrap-break-word min-w-0 text-sm leading-relaxed text-danger/90">{message}</p>
    </div>
  );
}
