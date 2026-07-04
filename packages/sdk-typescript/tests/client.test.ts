import { describe, expect, it } from "vitest";

import { MemriseClient } from "../src/client.js";
import { MemoryClientError } from "../src/errors.js";

describe("MemoryClientError", () => {
  it("exposes status code and structured error code", () => {
    const error = new MemoryClientError("bad request", {
      status: 422,
      code: "validation_error",
      requestId: "req_1",
    });
    expect(error.status).toBe(422);
    expect(error.code).toBe("validation_error");
    expect(error.requestId).toBe("req_1");
  });
});

describe("MemriseClient", () => {
  it("maps ergonomic capture input to the OpenAPI transport body", async () => {
    let body: unknown;
    const client = new MemriseClient({
      baseUrl: "http://localhost:8000",
      apiKey: "test-key",
      fetchImpl: async (_url, init) => {
        body = JSON.parse(String(init?.body));
        return new Response(JSON.stringify({ episode_ids: ["ep_1"], job_ids: ["job_1"] }), {
          status: 202,
          headers: { "content-type": "application/json" },
        });
      },
    });

    await client.capture({
      namespaceId: "local",
      agentId: "coding-agent",
      sessionId: "s1",
      projectId: "atlas",
      events: [{ kind: "user_message", content: "Atlas uses pnpm." }],
    });

    expect(body).toEqual({
      namespace_id: "local",
      agent_id: "coding-agent",
      session_id: "s1",
      project_id: "atlas",
      events: [{ kind: "user_message", content: "Atlas uses pnpm." }],
    });
  });

  it("lists retrievals with namespace and limit query params", async () => {
    let url = "";
    const client = new MemriseClient({
      baseUrl: "http://localhost:8000",
      apiKey: "test-key",
      fetchImpl: async (requestUrl) => {
        url = String(requestUrl);
        return new Response(
          JSON.stringify([
            {
              id: "ret_1",
              namespace_id: "local",
              agent_id: "coding-agent",
              query: "Atlas deps",
              task_type: null,
              project_id: "atlas",
              token_budget: 800,
              created_at: "2026-07-02T12:00:00Z",
            },
          ]),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      },
    });

    const traces = await client.listRetrievals({ namespaceId: "local", limit: 20 });
    expect(url).toBe("http://localhost:8000/v1/retrievals?namespace_id=local&limit=20");
    expect(traces).toHaveLength(1);
    expect(traces[0]?.id).toBe("ret_1");
  });

  it("calls health endpoints", async () => {
    const calls: string[] = [];
    const client = new MemriseClient({
      baseUrl: "http://localhost:8000",
      apiKey: "test-key",
      fetchImpl: async (requestUrl) => {
        calls.push(String(requestUrl));
        return new Response(JSON.stringify({ status: "ok", database: "connected" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      },
    });

    await client.healthLive();
    await client.healthReady();
    expect(calls).toEqual([
      "http://localhost:8000/health/live",
      "http://localhost:8000/health/ready",
    ]);
  });

  it("lists session episodes with snake_case query params", async () => {
    let url = "";
    const client = new MemriseClient({
      baseUrl: "http://localhost:8000",
      apiKey: "test-key",
      fetchImpl: async (input) => {
        url = String(input);
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      },
    });

    await client.listSessionEpisodes({
      namespaceId: "ns",
      agentId: "agent",
      sessionId: "session-1",
    });

    expect(url).toContain("/v1/episodes?");
    expect(url).toContain("namespace_id=ns");
    expect(url).toContain("session_id=session-1");
  });

  it("lists episode candidates by id", async () => {
    let url = "";
    const client = new MemriseClient({
      baseUrl: "http://localhost:8000",
      apiKey: "test-key",
      fetchImpl: async (input) => {
        url = String(input);
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      },
    });

    await client.listEpisodeCandidates("ep_1");

    expect(url).toContain("/v1/episodes/ep_1/candidates");
  });

  it("runs the lifecycle sweep", async () => {
    let url = "";
    let method = "";
    const client = new MemriseClient({
      baseUrl: "http://localhost:8000",
      apiKey: "test-key",
      fetchImpl: async (input, init) => {
        url = String(input);
        method = String(init?.method);
        return new Response(
          JSON.stringify({
            expired_memory_versions: 1,
            decayed_versions: 2,
            resolved_contested: 0,
            expired_claims: 0,
            expired_edges: 0,
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      },
    });

    const result = await client.runLifecycle();

    expect(url).toContain("/v1/lifecycle/run");
    expect(method).toBe("POST");
    expect(result.expired_memory_versions).toBe(1);
  });

  it("forwards the status filter when listing memories", async () => {
    let url = "";
    const client = new MemriseClient({
      baseUrl: "http://localhost:8000",
      apiKey: "test-key",
      fetchImpl: async (input) => {
        url = String(input);
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      },
    });

    await client.listMemories({ namespaceId: "ns", agentId: "agent", status: "contested" });

    expect(url).toContain("status=contested");
  });
});
