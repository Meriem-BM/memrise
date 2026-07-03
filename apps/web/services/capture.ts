import type { MemriseClient } from "memrise-memory-sdk";

import { LOCAL_INSPECTOR_SCOPE } from "@/lib/scope";
import type { CaptureResult, JobSummary } from "@/types/memory";

export async function captureMessage(
  client: MemriseClient,
  message: string,
): Promise<CaptureResult> {
  const startedAt = Date.now();
  const captureResult = await client.capture({
    ...LOCAL_INSPECTOR_SCOPE,
    events: [{ kind: "user_message", content: message, metadata: {} }],
  });

  if (captureResult.job_ids.length === 0) {
    return {
      episodeIds: captureResult.episode_ids,
      jobs: [],
      memories: [],
      skippedExtraction: true,
    };
  }

  const jobs: JobSummary[] = [];
  for (const jobId of captureResult.job_ids) {
    const job = await client.waitForJob(jobId, { timeoutMs: 120_000, pollMs: 500 });
    jobs.push(job);
  }

  const listed = await client.listMemories({
    namespaceId: LOCAL_INSPECTOR_SCOPE.namespaceId,
    agentId: LOCAL_INSPECTOR_SCOPE.agentId,
    projectId: LOCAL_INSPECTOR_SCOPE.projectId,
  });
  const memories = listed.filter((memory) => Date.parse(memory.created_at) >= startedAt - 5_000);

  return {
    episodeIds: captureResult.episode_ids,
    jobs,
    memories,
    skippedExtraction: false,
  };
}
