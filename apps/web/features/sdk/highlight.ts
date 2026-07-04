import "server-only";

import { createHighlighter, type Highlighter } from "shiki";

export type HighlightLanguage = "ts" | "bash";

type Highlightable = { id: string; code: string; language: HighlightLanguage };

let highlighterPromise: Promise<Highlighter> | null = null;

function getHighlighter(): Promise<Highlighter> {
  highlighterPromise ??= createHighlighter({
    themes: ["night-owl"],
    langs: ["typescript", "bash"],
  });
  return highlighterPromise;
}

export async function highlightCode(code: string, language: HighlightLanguage): Promise<string> {
  const highlighter = await getHighlighter();
  return highlighter.codeToHtml(code, {
    lang: language === "bash" ? "bash" : "typescript",
    theme: "night-owl",
  });
}

/** Pre-render each item's code to highlighted HTML, keyed by id, on the server. */
export async function highlightAll(items: Highlightable[]): Promise<Record<string, string>> {
  const pairs = await Promise.all(
    items.map(async (item) => [item.id, await highlightCode(item.code, item.language)] as const),
  );
  return Object.fromEntries(pairs);
}
