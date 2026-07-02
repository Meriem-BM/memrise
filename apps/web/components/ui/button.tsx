import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

type Variant = "primary" | "ghost" | "subtle";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant };

const base =
  "focus-ring inline-flex h-11 items-center justify-center gap-2 rounded-xl px-5 text-sm font-semibold transition-all duration-200 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50";

const variants: Record<Variant, string> = {
  primary: "bg-white text-black hover:bg-white/90",
  ghost: "border border-white/10 bg-black text-white hover:bg-white/5",
  subtle: "bg-surface text-white/60 hover:text-white",
};

export function Button({ className, variant = "primary", ...props }: ButtonProps) {
  return <button className={cn(base, variants[variant], className)} {...props} />;
}
