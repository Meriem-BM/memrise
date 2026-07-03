import type { components } from "memrise-memory-sdk";

export type MemorySummary = components["schemas"]["MemorySummary"];
export type JobSummary = components["schemas"]["JobSummary"];

/** Inspector view model for the playground capture flow. */
export type CaptureResult = {
  episodeIds: string[];
  jobs: JobSummary[];
  memories: MemorySummary[];
  skippedExtraction: boolean;
};
