import type { TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        "min-h-28 w-full resize-y rounded border border-[var(--border)] bg-white px-3 py-2 text-sm outline-none focus:border-teal-700",
        className,
      )}
      {...props}
    />
  );
}
