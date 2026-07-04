"use client";

import { Check, Copy } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { createHighlighter, type Highlighter } from "shiki";

import { ClientOnly } from "@/components/client-only";
import { INSTALL, SNIPPETS, type Snippet } from "@/features/sdk/snippets";

let sharedHighlighter: Highlighter | null = null;
let highlighterInitPromise: Promise<Highlighter> | null = null;

async function getSharedHighlighter(): Promise<Highlighter> {
  if (sharedHighlighter) return sharedHighlighter;
  if (highlighterInitPromise) return highlighterInitPromise;

  highlighterInitPromise = createHighlighter({
    themes: ["github-dark"],
    langs: ["typescript", "bash"],
  }).then((h) => {
    sharedHighlighter = h;
    return h;
  });

  return highlighterInitPromise;
}

export function SdkPage() {
  return (
    <div className="mx-auto max-w-5xl">
      <div className="py-20 text-center">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/70">
          <span className="size-2 rounded-full bg-emerald-400" />
          <span>Framework-independent memory engine</span>
        </div>
        <h1 className="text-6xl font-semibold tracking-tight text-white">
          Give your agent a memory.
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-muted">
          Five simple calls: capture what happens, retrieve what matters, tell it what helped,
          consolidate what it learned. The console is built on exactly these — open it and see.
        </p>
        <div className="mt-10 flex items-center justify-center gap-4">
          <Link
            href="/console"
            className="inline-flex items-center gap-2 rounded-full bg-white px-8 py-4 text-base font-semibold text-black transition-transform hover:scale-105"
          >
            Open the console
          </Link>
          <a
            href="/api/memrise/openapi.json"
            className="inline-flex items-center gap-2 rounded-full border border-white/20 px-8 py-4 text-base font-medium text-white/80 transition-colors hover:bg-white/5 hover:text-white"
          >
            View API docs
          </a>
        </div>
      </div>

      <div className="space-y-8 pb-24">
        <div className="text-center">
          <h2 className="text-2xl font-semibold text-white">Quick start</h2>
          <p className="mt-2 text-muted">Get started in under a minute</p>
        </div>
        <SnippetBlock snippet={INSTALL} />
        {SNIPPETS.map((snippet) => (
          <SnippetBlock key={snippet.id} snippet={snippet} />
        ))}
      </div>
    </div>
  );
}

function SnippetBlock({ snippet }: { snippet: Snippet }) {
  const [copied, setCopied] = useState(false);
  const [highlightedCode, setHighlightedCode] = useState<string>("");

  useEffect(() => {
    async function highlight() {
      const highlighter = await getSharedHighlighter();
      const lang = snippet.language === "ts" ? "typescript" : "bash";
      const html = highlighter.codeToHtml(snippet.code, {
        lang,
        theme: "github-dark",
      });
      setHighlightedCode(html);
    }
    highlight();
  }, [snippet.code, snippet.language]);

  const copy = async () => {
    await navigator.clipboard.writeText(snippet.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <section className="overflow-hidden rounded-2xl border border-border bg-[#0d1117] shadow-2xl">
      <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
        <h2 className="text-base font-semibold text-white/90">{snippet.title}</h2>
        <button
          type="button"
          onClick={copy}
          className="rounded-lg bg-white/5 px-3 py-1.5 text-white/40 transition-colors hover:bg-white/10 hover:text-white"
          aria-label={`Copy ${snippet.title}`}
        >
          <ClientOnly fallback={<span className="inline-block size-3.5" aria-hidden />}>
            {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
          </ClientOnly>
        </button>
      </div>
      <div className="overflow-x-auto p-5">
        {highlightedCode ? (
          <div
            className="font-mono text-sm leading-relaxed"
            dangerouslySetInnerHTML={{ __html: highlightedCode }}
          />
        ) : (
          <pre className="font-mono text-sm leading-relaxed text-muted">{snippet.code}</pre>
        )}
      </div>
    </section>
  );
}
