"use client";

import { useQuery } from "@tanstack/react-query";
import { Circle } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { getMemriseClient } from "@/lib/api";
import { cn } from "@/lib/utils/cn";

const nav = [
  ["/", "Status"],
  ["/playground", "Playground"],
  ["/memories", "Memories"],
  ["/retrievals", "Retrievals"],
  ["/graph", "Graph"],
];

export function SiteHeader() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-30 border-b border-white/10 bg-black/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-4">
        <Link href="/" className="flex items-center gap-2.5">
          <Circle size={18} className="fill-white text-white" />
          <span className="text-xl font-semibold tracking-tight">Memrise</span>
        </Link>

        <nav className="flex items-center gap-1 rounded-full border border-white/10 bg-surface p-1 text-sm">
          {nav.map(([href, label]) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "rounded-full px-4 py-1.5 font-medium transition-colors duration-200",
                  active ? "bg-white text-black" : "text-white/40 hover:text-white",
                )}
              >
                {label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
