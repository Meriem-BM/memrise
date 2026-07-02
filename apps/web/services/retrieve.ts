import type { MemriseClient } from "memrise-memory-sdk";

import { LOCAL_INSPECTOR_SCOPE } from "@/lib/scope";

type RetrievalPayload = {
  memories: Array<{ memory_version_id: string }>;
  critical: Array<{ memory_version_id: string }>;
};

export function pickPrimaryMemoryVersionId(data: RetrievalPayload): string | null {
  return data.memories[0]?.memory_version_id ?? data.critical[0]?.memory_version_id ?? null;
}

export function retrieveMemories(client: MemriseClient, query: string) {
  return client.retrieve({
    ...LOCAL_INSPECTOR_SCOPE,
    query,
    taskType: "dependency_install",
    tokenBudget: 800,
    limit: 10,
    graphHops: 1,
  });
}

export function submitHelpfulFeedback(
  client: MemriseClient,
  retrievalId: string,
  memoryVersionId: string,
) {
  return client.feedback(retrievalId, {
    outcome: "helpful",
    source: "developer",
    memoryVersionId,
  });
}
