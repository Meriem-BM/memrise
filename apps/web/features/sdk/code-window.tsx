"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { ClientOnly } from "@/components/client-only";
import { cn } from "@/lib/utils/cn";

export type CodePanel = {
  id: string;
  label?: string;
  filename: string;
  code: string;
  /** Pre-highlighted HTML from shiki (rendered on the server). */
  html: string;
};

function MacDots() {
  return (
    <div className="flex items-center gap-2" aria-hidden>
      <span className="size-3 rounded-full bg-[#ff5f57] shadow-[inset_0_0_0_0.5px_rgba(0,0,0,0.25)]" />
      <span className="size-3 rounded-full bg-[#febc2e] shadow-[inset_0_0_0_0.5px_rgba(0,0,0,0.25)]" />
      <span className="size-3 rounded-full bg-[#28c840] shadow-[inset_0_0_0_0.5px_rgba(0,0,0,0.25)]" />
    </div>
  );
}

function CopyButton({ code, label }: { code: string; label: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <button
      type="button"
      onClick={copy}
      aria-label={`Copy ${label}`}
      className="rounded-md p-1.5 text-white/35 transition-colors hover:bg-white/10 hover:text-white"
    >
      <ClientOnly fallback={<span className="inline-block size-3.5" aria-hidden />}>
        {copied ? <Check size={14} className="text-ok" /> : <Copy size={14} />}
      </ClientOnly>
    </button>
  );
}

/** A macOS-style window rendering server-highlighted (shiki) code. */
export function CodeWindow({
  panels,
  activeId,
  onTab,
  glow = false,
  className,
}: {
  panels: CodePanel[];
  activeId?: string;
  onTab?: (id: string) => void;
  glow?: boolean;
  className?: string;
}) {
  const active = panels.find((panel) => panel.id === activeId) ?? panels[0];
  const showTabs = panels.length > 1;

  return (
    <div className={cn("relative", className)}>
      {glow ? (
        <div
          aria-hidden
          className="pointer-events-none absolute -inset-x-10 -top-10 bottom-0 -z-10 rounded-[2.5rem] bg-[radial-gradient(50%_45%_at_50%_0%,color-mix(in_srgb,var(--accent)_18%,transparent),transparent_72%)] blur-2xl"
        />
      ) : null}
      <div className="overflow-hidden rounded-xl border border-white/10 bg-[#07080b] shadow-[0_24px_70px_-24px_rgba(0,0,0,0.9)]">
        <div className="flex items-center gap-4 border-b border-white/6 bg-white/1.5 px-4 py-3">
          <MacDots />
          {showTabs ? (
            <div className="flex items-center gap-1">
              {panels.map((panel) => (
                <button
                  key={panel.id}
                  type="button"
                  onClick={() => onTab?.(panel.id)}
                  className={cn(
                    "rounded-md px-3 py-1 font-mono text-xs transition-colors",
                    panel.id === active.id
                      ? "bg-white/10 text-white"
                      : "text-white/35 hover:text-white/70",
                  )}
                >
                  {panel.label ?? panel.filename}
                </button>
              ))}
            </div>
          ) : (
            <span className="font-mono text-xs text-white/40">{active.filename}</span>
          )}
          <div className="ml-auto flex items-center gap-2">
            {showTabs ? (
              <span className="hidden font-mono text-xs text-white/25 sm:inline">
                {active.filename}
              </span>
            ) : null}
            <CopyButton code={active.code} label={active.filename} />
          </div>
        </div>
        <div
          className="overflow-x-auto px-5 py-4 text-[13px] leading-[1.75] [&_code]:font-mono [&_pre]:m-0! [&_pre]:bg-transparent! [&_pre]:p-0!"
          dangerouslySetInnerHTML={{ __html: active.html }}
        />
      </div>
    </div>
  );
}
