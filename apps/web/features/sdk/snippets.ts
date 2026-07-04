export type Snippet = { id: string; title: string; language: "ts" | "bash"; code: string };

export const INSTALL: Snippet = {
  id: "install",
  title: "Install the SDK",
  language: "bash",
  code: "pnpm add memrise-memory-sdk",
};

export const SNIPPETS: Snippet[] = [
  {
    id: "client",
    title: "Initialize the client",
    language: "ts",
    code: `import { MemriseClient } from "memrise-memory-sdk";

const client = new MemriseClient({
  baseUrl: "http://localhost:8000",
  apiKey: process.env.MEMRISE_API_KEY, // omit in the browser behind a proxy
});`,
  },
  {
    id: "capture",
    title: "Capture conversations as episodes",
    language: "ts",
    code: `const result = await client.capture({
  namespaceId: "my-app",
  agentId: "assistant",
  sessionId: "session-1",
  events: [{ kind: "user_message", content: "We now use pnpm instead of npm.", metadata: {} }],
});
// extraction runs in the background:
await client.waitForJob(result.job_ids[0]);`,
  },
  {
    id: "retrieve",
    title: "Retrieve relevant context",
    language: "ts",
    code: `const memory = await client.retrieve({
  namespaceId: "my-app",
  agentId: "assistant",
  query: "which package manager do we use?",
  tokenBudget: 800,
});
console.log(memory.context); // ready to drop into your prompt`,
  },
  {
    id: "feedback",
    title: "Send feedback to improve memory",
    language: "ts",
    code: `await client.feedback(memory.retrieval_id, {
  outcome: "helpful",
  source: "agent",
  memoryVersionId: memory.memories[0].memory_version_id,
});`,
  },
  {
    id: "consolidate",
    title: "Consolidate session memories",
    language: "ts",
    code: `await client.consolidate("session-1", {
  namespaceId: "my-app",
  agentId: "assistant",
  sessionId: "session-1",
});`,
  },
  {
    id: "curl",
    title: "Use raw HTTP requests",
    language: "bash",
    code: `curl -X POST http://localhost:8000/v1/memories/retrieve \\
  -H "Authorization: Bearer $MEMRISE_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"namespace_id":"my-app","agent_id":"assistant","query":"which package manager?"}'`,
  },
];
