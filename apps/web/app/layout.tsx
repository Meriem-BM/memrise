import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { QueryProvider } from "@/lib/query-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Memrise inspector",
  description: "Inspector for the Memrise framework",
};

const nav = [
  ["/", "Status"],
  ["/playground", "Playground"],
  ["/memories", "Memories"],
  ["/retrievals", "Retrievals"],
  ["/graph", "Graph"],
  ["/evaluations", "Evaluations"],
];

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>
          <div className="min-h-screen">
            <header className="border-b border-[var(--border)] bg-white">
              <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
                <Link href="/" className="text-lg font-semibold">
                  Memrise
                </Link>
                <nav className="flex flex-wrap items-center gap-1 text-sm text-slate-600">
                  {nav.map(([href, label]) => (
                    <Link key={href} href={href} className="rounded px-3 py-2 hover:bg-slate-100">
                      {label}
                    </Link>
                  ))}
                </nav>
              </div>
            </header>
            <main className="mx-auto max-w-7xl px-6 py-6">{children}</main>
          </div>
        </QueryProvider>
      </body>
    </html>
  );
}
