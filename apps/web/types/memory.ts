export type MemorySummary = {
  memory_id: string;
  subject: string;
  key: string;
  content: string;
  status: string;
  type: string;
};

export type JobSummary = {
  id: string;
  type: string;
  status: string;
  last_error: string | null;
};

export type CaptureResult = {
  episodeIds: string[];
  jobs: JobSummary[];
  memories: MemorySummary[];
  skippedExtraction: boolean;
};
