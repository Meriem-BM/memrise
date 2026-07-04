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
    <div className="mx-auto max-w-4xl">
      <div className="py-16 text-center">
        <h1 className="text-5xl font-medium tracking-tight">Give your agent a memory.</h1>
        <p className="mx-auto mt-5 max-w-xl text-base leading-relaxed text-muted">
          Five calls: capture what happens, retrieve what matters, tell it what helped, consolidate
          what it learned. The console is built on exactly these — open it and see.
        </p>
        <Link
          href="/console"
          className="mt-8 inline-block rounded-full bg-white px-6 py-3 text-sm font-medium text-black transition-transform hover:scale-105"
        >
          Open the console
        </Link>
      </div>

      <div className="space-y-6 pb-20">
        <SnippetBlock snippet={INSTALL} />
        {SNIPPETS.map((snippet) => (
          <SnippetBlock key={snippet.id} snippet={snippet} />
        ))}
        <p className="pt-4 text-center text-sm text-faint">
          Full API reference:{" "}
          <a href="/api/memrise/openapi.json" className="underline hover:text-white">
            openapi.json
          </a>
        </p>
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
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <div className="size-3 rounded-full bg-red-500/80" />
            <div className="size-3 rounded-full bg-yellow-500/80" />
            <div className="size-3 rounded-full bg-green-500/80" />
          </div>
          <h2 className="ml-3 text-sm font-medium text-white/90">{snippet.title}</h2>
        </div>
        <button
          type="button"
          onClick={copy}
          className="text-white/40 transition-colors hover:text-white"
          aria-label={`Copy ${snippet.title}`}
        >
          <ClientOnly fallback={<span className="inline-block size-3.5" aria-hidden />}>
            {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
          </ClientOnly>
        </button>
      </div>
      <div className="overflow-x-auto p-4">
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
