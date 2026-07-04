"use client";

import { Check, Copy } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ClientOnly } from "@/components/client-only";
import { INSTALL, SNIPPETS, type Snippet } from "@/features/sdk/snippets";

export function SdkPage() {
  return (
    <div className="mx-auto max-w-3xl">
      <div className="py-10 text-center">
        <h1 className="text-4xl font-medium tracking-tight">Give your agent a memory.</h1>
        <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-muted">
          Five calls: capture what happens, retrieve what matters, tell it what helped, consolidate
          what it learned. The console is built on exactly these — open it and see.
        </p>
        <Link
          href="/console"
          className="mt-6 inline-block rounded-full bg-white px-5 py-2 text-sm font-medium text-black"
        >
          Open the console
        </Link>
      </div>

      <div className="space-y-4 pb-16">
        <SnippetBlock snippet={INSTALL} />
        {SNIPPETS.map((snippet) => (
          <SnippetBlock key={snippet.id} snippet={snippet} />
        ))}
        <p className="pt-2 text-center text-xs text-faint">
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
  const copy = async () => {
    await navigator.clipboard.writeText(snippet.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <section className="rounded-2xl border border-border bg-white/2">
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <h2 className="text-sm font-medium">{snippet.title}</h2>
        <button
          type="button"
          onClick={copy}
          className="text-white/40 transition-colors hover:text-white"
          aria-label={`Copy ${snippet.title}`}
        >
          <ClientOnly fallback={<span className="inline-block size-3.5" aria-hidden />}>
            {copied ? <Check size={14} className="text-ok" /> : <Copy size={14} />}
          </ClientOnly>
        </button>
      </div>
      <pre className="overflow-x-auto p-4 font-mono text-xs leading-relaxed text-muted">
        {snippet.code}
      </pre>
    </section>
  );
}
