import type { TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        "min-h-28 w-full resize-y rounded-xl border-none bg-elevated px-4 py-3 text-sm leading-relaxed text-white outline-none transition-shadow placeholder:text-white/20 focus:ring-2 focus:ring-white/20",
        className,
      )}
      {...props}
    />
  );
}
