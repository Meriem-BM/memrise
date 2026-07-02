import type { InputHTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-11 w-full rounded-xl border-none bg-elevated px-4 text-sm text-white outline-none transition-shadow placeholder:text-white/20 focus:ring-2 focus:ring-white/20",
        className,
      )}
      {...props}
    />
  );
}
