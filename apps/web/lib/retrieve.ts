import type { components } from "memrise-memory-sdk";

export type RetrieveResponse = components["schemas"]["RetrieveResponse"];
export type RetrievedMemory = RetrieveResponse["memories"][number];
// RetrievalItemSummary shape from GET /v1/retrievals/{id}; keep structural to
// avoid depending on an SDK named export that may not exist.
export type RetrievalItemLike = {
  memory_version_id: string | null;
  final_rank: number;
  lexical_score: number | null;
  semantic_score: number | null;
  graph_score: number | null;
  source_type: string;
};

export type ChannelScores = { lexical?: number; semantic?: number; graph?: number };

export type RetrievalRow = {
  memory: RetrievedMemory;
  critical: boolean;
  scores: ChannelScores;
  rank?: number;
  sourceType?: string;
};

export function buildRetrievalRows(
  response: RetrieveResponse,
  items: RetrievalItemLike[],
): RetrievalRow[] {
  const byVersionId = new Map<string, RetrievalItemLike>();
  for (const item of items) {
    if (item.memory_version_id) {
      byVersionId.set(item.memory_version_id, item);
    }
  }

  const toRow = (memory: RetrievedMemory, critical: boolean): RetrievalRow => {
    const item = byVersionId.get(memory.memory_version_id);
    const scores: ChannelScores = {};
    if (item?.lexical_score != null) scores.lexical = item.lexical_score;
    if (item?.semantic_score != null) scores.semantic = item.semantic_score;
    if (item?.graph_score != null) scores.graph = item.graph_score;
    return { memory, critical, scores, rank: item?.final_rank, sourceType: item?.source_type };
  };

  const ranked = response.memories
    .map((memory: RetrievedMemory) => toRow(memory, false))
    .sort(
      (a: RetrievalRow, b: RetrievalRow) =>
        (a.rank ?? Number.MAX_SAFE_INTEGER) - (b.rank ?? Number.MAX_SAFE_INTEGER),
    );

  return [...response.critical.map((memory: RetrievedMemory) => toRow(memory, true)), ...ranked];
}
