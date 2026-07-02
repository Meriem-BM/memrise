import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

type Variant = "default" | "ok" | "warn" | "danger" | "inverted";

const variants: Record<Variant, string> = {
  default: "border-white/10 bg-white/6 text-white/60",
  ok: "border-white/10 bg-white/6 text-ok",
  warn: "border-white/10 bg-white/6 text-warn",
  danger: "border-white/10 bg-white/6 text-danger",
  inverted: "border-white/20 bg-white text-black",
};

/** map common status / criticality strings to a color variant */
export function statusVariant(value?: string | null): Variant {
  switch (value) {
    case "active":
    case "ok":
    case "completed":
    case "helpful":
      return "ok";
    case "contested":
    case "pending":
    case "high_priority":
      return "warn";
    case "failed":
    case "deprecated":
    case "retired":
      return "danger";
    case "must_include":
    case "critical":
      return "inverted";
    default:
      return "default";
  }
}

type BadgeProps = HTMLAttributes<HTMLSpanElement> & { variant?: Variant };

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-medium leading-5",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
