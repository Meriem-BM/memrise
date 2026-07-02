import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

type CardProps = HTMLAttributes<HTMLDivElement> & {
  /** enable hover lift */
  interactive?: boolean;
};

export function Card({ className, interactive, children, ...props }: CardProps) {
  return (
    <section
      className={cn(
        "rounded-2xl border border-white/10 bg-surface p-6",
        interactive && "hover-lift",
        className,
      )}
      {...props}
    >
      {children}
    </section>
  );
}

export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2 className={cn("text-sm font-semibold tracking-tight text-white", className)} {...props} />
  );
}
