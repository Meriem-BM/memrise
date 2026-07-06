"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { CodeWindow, type CodePanel } from "@/features/sdk/code-window";
import { Features } from "@/features/sdk/features";
import { HERO_TABS, INSTALL, SNIPPETS } from "@/features/sdk/snippets";

export function SdkPage({ highlighted }: { highlighted: Record<string, string> }) {
  const [heroTab, setHeroTab] = useState(HERO_TABS[0].id);

  const heroPanels: CodePanel[] = HERO_TABS.map((tab) => ({
    id: tab.id,
    label: tab.label,
    filename: tab.filename,
    code: tab.code,
    html: highlighted[tab.id] ?? "",
  }));
  const panelFor = (snippet: (typeof SNIPPETS)[number] | typeof INSTALL): CodePanel => ({
    id: snippet.id,
    filename: snippet.filename,
    code: snippet.code,
    html: highlighted[snippet.id] ?? "",
  });

  return (
    <div className="mx-auto max-w-5xl px-2">
      {/* Hero */}
      <section className="pt-16 pb-10 text-center sm:pt-24">
        <h1 className="mx-auto max-w-3xl text-balance text-5xl font-semibold leading-[1.05] tracking-tight text-white sm:text-6xl">
          Give your agent a memory
          <span className="text-white/30"> that actually sticks.</span>
        </h1>
        <p className="mx-auto mt-6 max-w-xl text-base leading-relaxed text-muted sm:text-lg">
          Capture what happens, recall what matters, and let it learn over time. A few calls, and
          your agent stops forgetting.
        </p>
        <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/console"
            className="group inline-flex items-center gap-2 rounded-full bg-white px-6 py-3 text-sm font-semibold text-black transition-transform hover:-translate-y-0.5"
          >
            Open the console
            <ArrowRight size={16} className="transition-transform group-hover:translate-x-0.5" />
          </Link>
          <a
            href="/api/memrise/openapi.json"
            className="inline-flex items-center gap-2 rounded-full border border-white/15 px-6 py-3 text-sm font-medium text-white/75 transition-colors hover:border-white/30 hover:text-white"
          >
            API reference
          </a>
        </div>

        <div className="mx-auto mt-14 max-w-3xl text-left">
          <CodeWindow panels={heroPanels} activeId={heroTab} onTab={setHeroTab} glow />
        </div>
      </section>

      {/* Feature bento */}
      <Features />

      {/* The five calls */}
      <section className="py-14">
        <div className="mb-8 text-center">
          <h2 className="text-2xl font-semibold tracking-tight text-white">
            Five calls. That&rsquo;s the whole API.
          </h2>
          <p className="mt-2 text-sm text-muted">
            Start with <span className="font-mono text-white/70">pnpm add memrise-memory-sdk</span>.
          </p>
        </div>

        <div className="space-y-5">
          <CodeWindow panels={[panelFor(INSTALL)]} />
          {SNIPPETS.map((snippet) => (
            <div key={snippet.id}>
              <p className="mb-2 pl-1 text-sm font-medium text-white/80">{snippet.title}</p>
              <CodeWindow panels={[panelFor(snippet)]} />
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col items-center gap-4 rounded-2xl border border-border bg-panel px-6 py-10 text-center">
          <h3 className="text-xl font-medium text-white">See it think.</h3>
          <p className="max-w-md text-sm text-muted">
            The console runs this exact loop live. Every prompt recalls, learns, and grows the
            knowledge graph in front of you.
          </p>
          <Link
            href="/console"
            className="group inline-flex items-center gap-2 rounded-full bg-white px-6 py-3 text-sm font-semibold text-black transition-transform hover:-translate-y-0.5"
          >
            Open the console
            <ArrowRight size={16} className="transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>
      </section>
    </div>
  );
}
