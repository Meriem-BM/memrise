import type { paths } from "./generated/api-types.js";

type CaptureBody = paths["/v1/episodes"]["post"]["requestBody"]["content"]["application/json"];
type RememberBody = paths["/v1/memories"]["post"]["requestBody"]["content"]["application/json"];
type FeedbackBody =
  paths["/v1/retrievals/{retrieval_id}/feedback"]["post"]["requestBody"]["content"]["application/json"];

export interface CaptureEventInput {
  kind: CaptureBody["events"][number]["kind"];
  content: string;
  metadata?: Record<string, unknown>;
}

export interface CaptureInput {
  namespaceId: string;
  agentId: string;
  sessionId: string;
  userId?: string;
  projectId?: string;
  events: CaptureEventInput[];
}

export interface RememberInput {
  namespaceId: string;
  agentId: string;
  subject: string;
  key: string;
  content: string;
  type: RememberBody["type"];
  userId?: string;
  projectId?: string;
  structuredValue?: Record<string, unknown>;
  confidence?: number;
  importance?: number;
  criticality?: RememberBody["criticality"];
  applicability?: Record<string, unknown>;
  sourceEpisodeContent?: string;
  sourceEpisodeMetadata?: Record<string, unknown>;
  graphRelations?: [string, string, string][];
  validUntil?: string;
}

export interface RetrieveInput {
  namespaceId: string;
  agentId: string;
  query: string;
  userId?: string;
  projectId?: string;
  taskType?: string;
  tokenBudget?: number;
  limit?: number;
  graphHops?: number;
}

export interface FeedbackInput {
  outcome: FeedbackBody["outcome"];
  source: FeedbackBody["source"];
  memoryVersionId?: string;
  graphEdgeId?: string;
  confidence?: number;
  taskType?: string;
}

export interface ConsolidateInput {
  namespaceId: string;
  agentId: string;
  sessionId: string;
  userId?: string;
  projectId?: string;
}

export interface MemriseClientOptions {
  baseUrl: string;
  apiKey: string;
  timeoutMs?: number;
  fetchImpl?: typeof fetch;
}

export type MemoryClientOptions = MemriseClientOptions;

export type HealthLiveResponse =
  paths["/health/live"]["get"]["responses"]["200"]["content"]["application/json"];
export type HealthReadyResponse =
  paths["/health/ready"]["get"]["responses"]["200"]["content"]["application/json"];
export type RetrievalTraceSummary =
  paths["/v1/retrievals"]["get"]["responses"]["200"]["content"]["application/json"][number];
