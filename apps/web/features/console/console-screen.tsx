"use client";

import { Loader2, Plus } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { ClientOnly } from "@/components/client-only";
import { GraphPanel } from "@/features/console/graph-panel";
import { TracePanel } from "@/features/console/trace-panel";
import { turnSummary } from "@/lib/console";
import { cn } from "@/lib/utils/cn";
import { useConsole } from "@/hooks/useConsole";

export function ConsoleScreen() {
  const consoleState = useConsole();
  const {
    entries,
    selectedId,
    select,
    submit,
    newSession,
    sessionId,
    memriseEnabled,
    setMemriseEnabled,
  } = consoleState;
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries.length]);

  const selected =
    entries.find((entry) => entry.kind === "turn" && entry.id === selectedId) ?? null;
  const selectedTurn = selected && selected.kind === "turn" ? selected : null;

  const onSubmit = async () => {
    const prompt = draft.trim();
    if (!prompt || busy) return;
    setDraft("");
    setBusy(true);
    try {
      await submit(prompt);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
      <section className="flex min-h-[75vh] flex-col rounded-2xl border border-border bg-panel">
        <header className="flex items-center justify-between gap-3 border-b border-border px-4 py-2.5">
          <p className="font-mono text-xs text-faint">
            memrise <span className="text-white/30">›</span>{" "}
            <ClientOnly fallback="session-starting">{sessionId}</ClientOnly>
          </p>
          <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              role="switch"
              aria-checked={memriseEnabled}
              aria-label={memriseEnabled ? "Deactivate Memrise" : "Activate Memrise"}
              onClick={() => setMemriseEnabled((current) => !current)}
              className="group inline-flex items-center gap-2 font-mono text-[11px] transition-transform active:scale-[0.97]"
            >
              <span
                className={cn(
                  "inline-flex h-5 w-9 items-center rounded-full border transition-colors",
                  memriseEnabled
                    ? "border-violet-300/40 bg-violet-300/25"
                    : "border-white/15 bg-white/5",
                )}
                aria-hidden
              >
                <span
                  className={cn(
                    "size-3.5 rounded-full transition-transform duration-200 ease-out",
                    memriseEnabled
                      ? "translate-x-[18px] bg-violet-200"
                      : "translate-x-0.5 bg-white/45 group-hover:bg-white/70",
                  )}
                />
              </span>
              <span className={memriseEnabled ? "text-violet-100" : "text-white/50"}>Memrise</span>
            </button>
            <button
              type="button"
              onClick={newSession}
              className="inline-flex h-8 items-center gap-1.5 rounded-full border border-white/10 px-3 text-xs text-white/50 transition-colors hover:text-white"
            >
              <ClientOnly fallback={<span className="inline-block size-3.5" aria-hidden />}>
                <Plus size={13} />
              </ClientOnly>
              new session
            </button>
          </div>
        </header>

        <div className="flex-1 space-y-3 overflow-y-auto p-4 font-mono text-sm leading-relaxed">
          {entries.length === 0 ? (
            <p className="text-faint">
              Tell the agent something worth remembering, or ask what it knows. Every prompt recalls
              and learns at once.
            </p>
          ) : null}
          {entries.map((entry) =>
            entry.kind === "notice" ? (
              <p key={entry.id} className="text-xs text-faint">
                {entry.text}
              </p>
            ) : (
              <button
                key={entry.id}
                type="button"
                onClick={() => select(entry.id)}
                className={cn(
                  "block w-full rounded-lg border px-3 py-2 text-left transition-colors",
                  entry.id === selectedId
                    ? "border-white/25 bg-white/4"
                    : "border-transparent hover:border-white/10",
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="wrap-break-word min-w-0">
                    <span className="text-white/35">&gt; </span>
                    {entry.prompt}
                  </p>
                  <span
                    className={cn(
                      "shrink-0 rounded-full border px-2 py-0.5 font-mono text-[10px]",
                      entry.memoryEnabled
                        ? "border-violet-300/30 text-violet-100/80"
                        : "border-white/10 text-white/35",
                    )}
                  >
                    {entry.memoryEnabled ? "Memrise on" : "Memrise off"}
                  </span>
                </div>
                {entry.answer.text ? (
                  <p className="mt-2 whitespace-pre-wrap text-[15px] leading-relaxed text-white">
                    {entry.answer.text}
                  </p>
                ) : null}
                <p className="mt-1 text-xs text-muted">
                  {turnSummary(entry.answer, entry.recall, entry.learn)}
                </p>
                {entry.answer.error ? (
                  <p className="mt-1 text-xs text-danger">{entry.answer.error}</p>
                ) : null}
                {entry.recall.error ? (
                  <p className="mt-1 text-xs text-danger">{entry.recall.error}</p>
                ) : null}
                {entry.learn.error ? (
                  <p className="mt-1 text-xs text-danger">{entry.learn.error}</p>
                ) : null}
              </button>
            ),
          )}
          <div ref={bottomRef} />
        </div>

        <footer className="border-t border-border p-3">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm text-white/35">&gt;</span>
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.nativeEvent.isComposing) return;
                if (event.key === "Enter") void onSubmit();
              }}
              placeholder="talk to the memory…"
              className="w-full bg-transparent font-mono text-sm text-white placeholder:text-white/25 focus:outline-none"
            />
            {busy ? (
              <ClientOnly fallback={<span className="inline-block size-4" aria-hidden />}>
                <Loader2 size={15} className="animate-spin text-muted" />
              </ClientOnly>
            ) : null}
          </div>
        </footer>
      </section>

      <aside className="flex min-h-[75vh] flex-col gap-4">
        <TracePanel
          turn={selectedTurn}
          feedbackFor={consoleState.feedbackFor}
          feedbackScores={consoleState.feedbackScores}
        />
        <GraphPanel
          graphQuery={selectedTurn?.memoryEnabled === false ? null : consoleState.graphQuery}
          turn={selectedTurn}
        />
      </aside>
    </div>
  );
}
