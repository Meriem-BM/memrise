import type { InputHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-9 w-full rounded border border-[var(--border)] bg-white px-3 text-sm outline-none focus:border-teal-700",
        className,
      )}
      {...props}
    />
  );
}
