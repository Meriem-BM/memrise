import type { paths } from "./generated/api-types.js";

type JobResponse =
  paths["/v1/jobs/{job_id}"]["get"]["responses"]["200"]["content"]["application/json"];

export function sleep(ms: number, signal: AbortSignal | undefined): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    const timeout = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(timeout);
        reject(new DOMException("Aborted", "AbortError"));
      },
      { once: true },
    );
  });
}

export async function waitForJobCompletion(
  getJob: (jobId: string, options?: { signal?: AbortSignal }) => Promise<JobResponse>,
  jobId: string,
  options: { signal?: AbortSignal; timeoutMs?: number; pollMs?: number } = {},
): Promise<JobResponse> {
  const timeoutMs = options.timeoutMs ?? 30_000;
  const pollMs = options.pollMs ?? 250;
  const started = Date.now();
  while (true) {
    const job = await getJob(jobId, options.signal ? { signal: options.signal } : {});
    if (job.status === "completed" || job.status === "failed") {
      return job;
    }
    if (Date.now() - started >= timeoutMs) {
      return job;
    }
    await sleep(pollMs, options.signal);
  }
}
