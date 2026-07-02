import type { paths } from "./generated/api-types.js";
import { MemoryClientError } from "./errors.js";

type CaptureBody = paths["/v1/episodes"]["post"]["requestBody"]["content"]["application/json"];
type CaptureResponse =
  paths["/v1/episodes"]["post"]["responses"]["202"]["content"]["application/json"];
type RetrieveBody =
  paths["/v1/memories/retrieve"]["post"]["requestBody"]["content"]["application/json"];
type RetrieveResponse =
  paths["/v1/memories/retrieve"]["post"]["responses"]["201"]["content"]["application/json"];
type FeedbackBody =
  paths["/v1/retrievals/{retrieval_id}/feedback"]["post"]["requestBody"]["content"]["application/json"];
type FeedbackResponse =
  paths["/v1/retrievals/{retrieval_id}/feedback"]["post"]["responses"]["201"]["content"]["application/json"];
type ConsolidateBody =
  paths["/v1/sessions/{session_id}/consolidate"]["post"]["requestBody"]["content"]["application/json"];
type ConsolidateResponse =
  paths["/v1/sessions/{session_id}/consolidate"]["post"]["responses"]["202"]["content"]["application/json"];
type ExplanationResponse =
  paths["/v1/memories/{memory_id}/explanation"]["get"]["responses"]["200"]["content"]["application/json"];

export interface MemoryClientOptions {
  baseUrl: string;
  apiKey: string;
  timeoutMs?: number;
  fetchImpl?: typeof fetch;
}

export class MemoryClient {
  readonly #baseUrl: string;
  readonly #apiKey: string;
  readonly #timeoutMs: number;
  readonly #fetch: typeof fetch;

  constructor(options: MemoryClientOptions) {
    this.#baseUrl = options.baseUrl.replace(/\/$/, "");
    this.#apiKey = options.apiKey;
    this.#timeoutMs = options.timeoutMs ?? 30_000;
    this.#fetch = options.fetchImpl ?? fetch;
  }

  capture(body: CaptureBody, options: { signal?: AbortSignal } = {}): Promise<CaptureResponse> {
    return this.#request("POST", "/v1/episodes", body, options.signal);
  }

  retrieve(body: RetrieveBody, options: { signal?: AbortSignal } = {}): Promise<RetrieveResponse> {
    return this.#request("POST", "/v1/memories/retrieve", body, options.signal);
  }

  feedback(
    retrievalId: string,
    body: FeedbackBody,
    options: { signal?: AbortSignal } = {},
  ): Promise<FeedbackResponse> {
    return this.#request(
      "POST",
      `/v1/retrievals/${encodeURIComponent(retrievalId)}/feedback`,
      body,
      options.signal,
    );
  }

  consolidate(
    sessionId: string,
    body: ConsolidateBody,
    options: { signal?: AbortSignal } = {},
  ): Promise<ConsolidateResponse> {
    return this.#request(
      "POST",
      `/v1/sessions/${encodeURIComponent(sessionId)}/consolidate`,
      body,
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
          "x-api-key": this.#apiKey,
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

function readError(value: unknown): { code: string; message: string } {
  if (
    typeof value === "object" &&
    value !== null &&
    "error" in value &&
    typeof value.error === "object" &&
    value.error !== null &&
    "code" in value.error &&
    "message" in value.error
  ) {
    return {
      code: String(value.error.code),
      message: String(value.error.message),
    };
  }
  return { code: "http_error", message: "request failed" };
}
