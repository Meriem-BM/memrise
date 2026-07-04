import type { paths } from "./generated/api-types.js";
import type {
  CaptureInput,
  ConsolidateInput,
  FeedbackInput,
  MemriseClientOptions,
  RememberInput,
  RespondInput,
  RetrieveInput,
} from "./client-types.js";
import { MemoryClientError } from "./errors.js";
import {
  readError,
  toCaptureBody,
  toConsolidateBody,
  toFeedbackBody,
  toQuery,
  toRememberBody,
  toRespondBody,
  toRetrieveBody,
} from "./mappers.js";
import { waitForJobCompletion } from "./polling.js";

type CaptureResponse =
  paths["/v1/episodes"]["post"]["responses"]["202"]["content"]["application/json"];
type RememberResponse =
  paths["/v1/memories"]["post"]["responses"]["201"]["content"]["application/json"];
type RetrieveResponse =
  paths["/v1/memories/retrieve"]["post"]["responses"]["201"]["content"]["application/json"];
type RespondResponse =
  paths["/v1/agent/respond"]["post"]["responses"]["201"]["content"]["application/json"];
type FeedbackResponse =
  paths["/v1/retrievals/{retrieval_id}/feedback"]["post"]["responses"]["201"]["content"]["application/json"];
type ConsolidateResponse =
  paths["/v1/sessions/{session_id}/consolidate"]["post"]["responses"]["202"]["content"]["application/json"];
type ExplanationResponse =
  paths["/v1/memories/{memory_id}/explanation"]["get"]["responses"]["200"]["content"]["application/json"];
type MemoryResponse =
  paths["/v1/memories/{memory_id}"]["get"]["responses"]["200"]["content"]["application/json"];
type VersionsResponse =
  paths["/v1/memories/{memory_id}/versions"]["get"]["responses"]["200"]["content"]["application/json"];
type RetrievalResponse =
  paths["/v1/retrievals/{retrieval_id}"]["get"]["responses"]["200"]["content"]["application/json"];
type GraphNeighborhoodResponse =
  paths["/v1/graph/neighborhood"]["get"]["responses"]["200"]["content"]["application/json"];
type JobResponse =
  paths["/v1/jobs/{job_id}"]["get"]["responses"]["200"]["content"]["application/json"];
type LifecycleRunResponse =
  paths["/v1/lifecycle/run"]["post"]["responses"]["200"]["content"]["application/json"];
type HealthLiveResponse =
  paths["/health/live"]["get"]["responses"]["200"]["content"]["application/json"];
type HealthReadyResponse =
  paths["/health/ready"]["get"]["responses"]["200"]["content"]["application/json"];
type RetrievalTraceSummary =
  paths["/v1/retrievals"]["get"]["responses"]["200"]["content"]["application/json"][number];
type EpisodeSummary =
  paths["/v1/episodes"]["get"]["responses"]["200"]["content"]["application/json"][number];
type CandidateStageSummary =
  paths["/v1/episodes/{episode_id}/candidates"]["get"]["responses"]["200"]["content"]["application/json"][number];
type JobSummary = JobResponse;
type MemoryStatus = NonNullable<paths["/v1/memories"]["get"]["parameters"]["query"]["status"]>;

export type { LifecycleRunResponse, MemoryStatus };

export type {
  CaptureEventInput,
  CaptureInput,
  ConsolidateInput,
  FeedbackInput,
  HealthLiveResponse,
  HealthReadyResponse,
  MemriseClientOptions,
  GraphRelationInput,
  RememberInput,
  RespondInput,
  RetrievalTraceSummary,
  RetrieveInput,
} from "./client-types.js";
export type { RespondResponse };
export type { CandidateStageSummary, EpisodeSummary, JobSummary };

export class MemriseClient {
  readonly #baseUrl: string;
  readonly #apiKey: string | undefined;
  readonly #timeoutMs: number;
  readonly #fetch: typeof fetch;

  constructor(options: MemriseClientOptions) {
    this.#baseUrl = options.baseUrl.replace(/\/$/, "");
    this.#apiKey = options.apiKey;
    this.#timeoutMs = options.timeoutMs ?? 30_000;
    this.#fetch = options.fetchImpl ?? ((input, init) => globalThis.fetch(input, init));
  }

  capture(body: CaptureInput, options: { signal?: AbortSignal } = {}): Promise<CaptureResponse> {
    return this.#request("POST", "/v1/episodes", toCaptureBody(body), options.signal);
  }

  remember(body: RememberInput, options: { signal?: AbortSignal } = {}): Promise<RememberResponse> {
    return this.#request("POST", "/v1/memories", toRememberBody(body), options.signal);
  }

  retrieve(body: RetrieveInput, options: { signal?: AbortSignal } = {}): Promise<RetrieveResponse> {
    return this.#request("POST", "/v1/memories/retrieve", toRetrieveBody(body), options.signal);
  }

  respond(body: RespondInput, options: { signal?: AbortSignal } = {}): Promise<RespondResponse> {
    return this.#request("POST", "/v1/agent/respond", toRespondBody(body), options.signal);
  }

  feedback(
    retrievalId: string,
    body: FeedbackInput,
    options: { signal?: AbortSignal } = {},
  ): Promise<FeedbackResponse> {
    return this.#request(
      "POST",
      `/v1/retrievals/${encodeURIComponent(retrievalId)}/feedback`,
      toFeedbackBody(body),
      options.signal,
    );
  }

  consolidate(
    sessionId: string,
    body: ConsolidateInput,
    options: { signal?: AbortSignal } = {},
  ): Promise<ConsolidateResponse> {
    return this.#request(
      "POST",
      `/v1/sessions/${encodeURIComponent(sessionId)}/consolidate`,
      toConsolidateBody(body),
      options.signal,
    );
  }

  explain(memoryId: string, options: { signal?: AbortSignal } = {}): Promise<ExplanationResponse> {
    return this.#request(
      "GET",
      `/v1/memories/${encodeURIComponent(memoryId)}/explanation`,
      undefined,
      options.signal,
    );
  }

  getMemory(memoryId: string, options: { signal?: AbortSignal } = {}): Promise<MemoryResponse> {
    return this.#request(
      "GET",
      `/v1/memories/${encodeURIComponent(memoryId)}`,
      undefined,
      options.signal,
    );
  }

  getMemoryVersions(
    memoryId: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<VersionsResponse> {
    return this.#request(
      "GET",
      `/v1/memories/${encodeURIComponent(memoryId)}/versions`,
      undefined,
      options.signal,
    );
  }

  listMemories(
    query: {
      namespaceId: string;
      agentId: string;
      userId?: string;
      projectId?: string;
      status?: MemoryStatus;
    },
    options: { signal?: AbortSignal } = {},
  ): Promise<MemoryResponse[]> {
    return this.#request(
      "GET",
      `/v1/memories?${toQuery({
        namespace_id: query.namespaceId,
        agent_id: query.agentId,
        user_id: query.userId,
        project_id: query.projectId,
        status: query.status,
      })}`,
      undefined,
      options.signal,
    );
  }

  listSessionEpisodes(
    query: {
      namespaceId: string;
      agentId: string;
      sessionId: string;
    },
    options: { signal?: AbortSignal } = {},
  ): Promise<EpisodeSummary[]> {
    return this.#request(
      "GET",
      `/v1/episodes?${toQuery({
        namespace_id: query.namespaceId,
        agent_id: query.agentId,
        session_id: query.sessionId,
      })}`,
      undefined,
      options.signal,
    );
  }

  listEpisodeCandidates(
    episodeId: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<CandidateStageSummary[]> {
    return this.#request(
      "GET",
      `/v1/episodes/${encodeURIComponent(episodeId)}/candidates`,
      undefined,
      options.signal,
    );
  }

  getRetrieval(
    retrievalId: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<RetrievalResponse> {
    return this.#request(
      "GET",
      `/v1/retrievals/${encodeURIComponent(retrievalId)}`,
      undefined,
      options.signal,
    );
  }

  listRetrievals(
    query: {
      namespaceId: string;
      limit?: number;
    },
    options: { signal?: AbortSignal } = {},
  ): Promise<RetrievalTraceSummary[]> {
    return this.#request(
      "GET",
      `/v1/retrievals?${toQuery({
        namespace_id: query.namespaceId,
        limit: query.limit,
      })}`,
      undefined,
      options.signal,
    );
  }

  graphNeighborhood(
    query: {
      namespaceId: string;
      agentId: string;
      userId?: string;
      projectId?: string;
      query?: string;
      hops?: number;
    },
    options: { signal?: AbortSignal } = {},
  ): Promise<GraphNeighborhoodResponse> {
    return this.#request(
      "GET",
      `/v1/graph/neighborhood?${toQuery({
        namespace_id: query.namespaceId,
        agent_id: query.agentId,
        user_id: query.userId,
        project_id: query.projectId,
        query: query.query,
        hops: query.hops,
      })}`,
      undefined,
      options.signal,
    );
  }

  getJob(jobId: string, options: { signal?: AbortSignal } = {}): Promise<JobResponse> {
    return this.#request("GET", `/v1/jobs/${encodeURIComponent(jobId)}`, undefined, options.signal);
  }

  async waitForJob(
    jobId: string,
    options: { signal?: AbortSignal; timeoutMs?: number; pollMs?: number } = {},
  ): Promise<JobResponse> {
    return waitForJobCompletion(
      (id, requestOptions) => this.getJob(id, requestOptions ?? {}),
      jobId,
      options,
    );
  }

  runLifecycle(options: { signal?: AbortSignal } = {}): Promise<LifecycleRunResponse> {
    return this.#request("POST", "/v1/lifecycle/run", undefined, options.signal);
  }

  healthLive(options: { signal?: AbortSignal } = {}): Promise<HealthLiveResponse> {
    return this.#request("GET", "/health/live", undefined, options.signal);
  }

  healthReady(options: { signal?: AbortSignal } = {}): Promise<HealthReadyResponse> {
    return this.#request("GET", "/health/ready", undefined, options.signal);
  }

  async #request<T>(
    method: "GET" | "POST",
    path: string,
    body: unknown,
    signal: AbortSignal | undefined,
  ): Promise<T> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.#timeoutMs);
    const abort = () => controller.abort();
    signal?.addEventListener("abort", abort, { once: true });
    try {
      const init: RequestInit = {
        method,
        signal: controller.signal,
        headers: {
          "content-type": "application/json",
          ...(this.#apiKey !== undefined ? { authorization: `Bearer ${this.#apiKey}` } : {}),
        },
      };
      if (body !== undefined) {
        init.body = JSON.stringify(body);
      }
      const response = await this.#fetch(`${this.#baseUrl}${path}`, init);
      const text = await response.text();
      const json = text.length > 0 ? (JSON.parse(text) as unknown) : null;
      if (!response.ok) {
        const error = readError(json);
        throw new MemoryClientError(error.message, {
          status: response.status,
          code: error.code,
          requestId: response.headers.get("x-request-id"),
        });
      }
      return json as T;
    } finally {
      clearTimeout(timeout);
      signal?.removeEventListener("abort", abort);
    }
  }
}
