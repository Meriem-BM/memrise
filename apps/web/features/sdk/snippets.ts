export type Snippet = {
  id: string;
  title: string;
  filename: string;
  language: "ts" | "bash";
  code: string;
};

export type HeroTab = {
  id: string;
  label: string;
  filename: string;
  language: "ts" | "bash";
  code: string;
};

/** Hero quickstart: the whole loop (learn then recall) in one script, per language. */
export const HERO_TABS: HeroTab[] = [
  {
    id: "ts",
    label: "TypeScript",
    filename: "quickstart.ts",
    language: "ts",
    code: `import { MemriseClient } from "memrise-memory-sdk";

const memory = new MemriseClient({ baseUrl: process.env.MEMRISE_URL });

// Learn: the agent remembers what just happened
await memory.capture({
  namespaceId: "acme",
  agentId: "assistant",
  sessionId: "session-42",
  events: [{ kind: "user_message", content: "We switched from npm to pnpm." }],
});

// Recall: ready to drop into the next prompt
const { context } = await memory.retrieve({
  namespaceId: "acme",
  agentId: "assistant",
  query: "which package manager do we use?",
});

console.log(context); // "- Acme uses pnpm for dependencies."`,
  },
  {
    id: "curl",
    label: "cURL",
    filename: "quickstart.sh",
    language: "bash",
    code: `# Learn
curl -X POST $MEMRISE_URL/v1/episodes \\
  -H "Authorization: Bearer $MEMRISE_API_KEY" \\
  -d '{"namespace_id":"acme","agent_id":"assistant","session_id":"session-42",
       "events":[{"kind":"user_message","content":"We switched from npm to pnpm."}]}'

# Recall
curl -X POST $MEMRISE_URL/v1/memories/retrieve \\
  -H "Authorization: Bearer $MEMRISE_API_KEY" \\
  -d '{"namespace_id":"acme","agent_id":"assistant","query":"which package manager?"}'`,
  },
];

export const INSTALL: Snippet = {
  id: "install",
  title: "Install",
  filename: "terminal",
  language: "bash",
  code: "pnpm add memrise-memory-sdk",
};

export const SNIPPETS: Snippet[] = [
  {
    id: "client",
    title: "Initialize the client",
    filename: "client.ts",
    language: "ts",
    code: `import { MemriseClient } from "memrise-memory-sdk";

const memory = new MemriseClient({
  baseUrl: "http://localhost:8000",
  apiKey: process.env.MEMRISE_API_KEY, // omit in the browser behind a proxy
});`,
  },
  {
    id: "capture",
    title: "Capture: turn conversation into memory",
    filename: "capture.ts",
    language: "ts",
    code: `const result = await memory.capture({
  namespaceId: "acme",
  agentId: "assistant",
  sessionId: "session-42",
  events: [{ kind: "user_message", content: "We now use pnpm instead of npm." }],
});

// extraction runs in the background
await memory.waitForJob(result.job_ids[0]);`,
  },
  {
    id: "retrieve",
    title: "Retrieve: pull the right context",
    filename: "retrieve.ts",
    language: "ts",
    code: `const memories = await memory.retrieve({
  namespaceId: "acme",
  agentId: "assistant",
  query: "which package manager do we use?",
  tokenBudget: 800,
});

console.log(memories.context); // ready to drop into your prompt`,
  },
  {
    id: "feedback",
    title: "Feedback: teach it what helped",
    filename: "feedback.ts",
    language: "ts",
    code: `await memory.feedback(memories.retrieval_id, {
  outcome: "helpful",
  source: "agent",
  memoryVersionId: memories.memories[0].memory_version_id,
});`,
  },
  {
    id: "consolidate",
    title: "Consolidate: distill a whole session",
    filename: "consolidate.ts",
    language: "ts",
    code: `await memory.consolidate("session-42", {
  namespaceId: "acme",
  agentId: "assistant",
  sessionId: "session-42",
});`,
  },
];
