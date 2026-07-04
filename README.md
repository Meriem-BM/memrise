# Memrise

**Memrise is a temporal, hybrid memory engine for AI agents.** It lets an agent autonomously accumulate experience, remember user preferences, forget what has gone stale, and recall the critical facts even inside a tight context window, across many turns and many sessions.

It stores experience as **immutable episodes**, consolidates durable knowledge into **versioned canonical memories**, projects accepted memories into a **temporal knowledge graph**, retrieves with **lexical + semantic + graph** signals fused together, and **learns from retrieval outcomes** without ever rewriting the truth it stored.

**PostgreSQL is the single source of truth** for episodes, canonical memories, embeddings, full-text search, graph claims, graph projection, retrieval traces, feedback, and background jobs.

---

## Table of contents

- [The problem this solves](#the-problem-this-solves)
- [System architecture](#system-architecture)
- [Models used for inference and embedding](#models-used-for-inference-and-embedding)
- [The write path: accumulating experience](#the-write-path-accumulating-experience)
- [The read path: recall under a context budget](#the-read-path-recall-under-a-context-budget)
- [Forgetting: keeping memory sharp over time](#forgetting-keeping-memory-sharp-over-time)
- [Outcome learning](#outcome-learning)
- [Memory lifecycle](#memory-lifecycle)
- [Data model](#data-model)
- [API & SDK surface](#api--sdk-surface)
- [Quick start](#quick-start)
- [Repository map](#repository-map)
- [Development](#development)
- [Current limitations](#current-limitations)

---

## The problem this solves

The hackathon brief asks for an agent that "autonomously accumulates experience, remembers user preferences, and makes increasingly accurate decisions across multi-turn, cross-session interactions," with a focus on **efficient storage and retrieval**, **timely forgetting of outdated information**, and **recalling critical memories within limited context windows**.

Memrise maps each of those to a concrete mechanism:

| Hackathon focus                            | How Memrise implements it                                                                                                                                                                                                                                                  |
| ------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Efficient storage & retrieval**          | Immutable episodes vs. versioned canonical memories; three retrieval channels (exact-lexical FTS, semantic pgvector, temporal graph) fused with Reciprocal Rank Fusion; per-channel candidate caps so cost is bounded.                                                     |
| **Timely forgetting**                      | A background lifecycle job that expires memories past their validity interval, **decays usefulness on a 30-day half-life toward neutral**, resolves contested pairs, and supersedes facts through temporal reconciliation, history is preserved, never physically deleted. |
| **Recall within a limited context window** | A **critical-memory reservation** (20% of the token budget, up to 3 `must_include` facts, packed first) plus a greedy token-budget packer and utility-aware ranking, so the constraints that matter survive even a small budget.                                           |

---

## System architecture

Agents talk to Memrise only through the **HTTP API** and the **TypeScript SDK**, never to PostgreSQL directly. The Python engine owns all memory logic; the worker runs background jobs; PostgreSQL (with pgvector + Apache AGE) is the source of truth; Qwen models provide extraction, consolidation, answering, and embeddings.

The diagram below is the target memory lifecycle; agents reach it through the Memory Gateway (the HTTP API + SDK).

![Memrise memory architecture](docs/memory-architecture.png)

---

## Models used for inference and embedding

All model access goes through the **Qwen adapter** (`packages/engine/src/memrise/integrations/qwen`), which speaks to **Alibaba Cloud DashScope** over its OpenAI-compatible endpoint. There is intentionally **no in-app model fallback**, capture, remember, retrieve, and respond require a configured API key.

| Purpose                                | Default model       | Config (env)           | Notes                                                                                                                          |
| -------------------------------------- | ------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **Memory extraction & classification** | `qwen3.6-flash`     | `QWEN_MEMORY_MODEL`    | Reads episode text, proposes candidate memories with type + criticality, emits validated JSON (`memory_extraction_v1` prompt). |
| **Session consolidation**              | `qwen3.6-flash`     | `QWEN_MEMORY_MODEL`    | Replays a session's episodes to consolidate durable knowledge (`consolidation_v1` prompt).                                     |
| **Agent answer generation**            | `qwen3.6-flash`     | `QWEN_MEMORY_MODEL`    | `POST /v1/agent/respond`: answers a query grounded in retrieved memories (`agent_answer_v1` prompt).                           |
| **Embeddings**                         | `text-embedding-v4` | `QWEN_EMBEDDING_MODEL` | **1024 dimensions** (`QWEN_EMBEDDING_DIMENSIONS`), stored in a pgvector column and used for the semantic retrieval channel.    |

Connection is configured with `ALIBABA_CLOUD_API_KEY` and `ALIBABA_CLOUD_BASE_URL`; calls use a 30s timeout (`QWEN_TIMEOUT_SECONDS`) and up to 2 retries (`QWEN_MAX_RETRIES`). Every stored memory version records the `embedding_model` and the extraction `model_name` / `prompt_version` for provenance.

---

## The write path: accumulating experience

An agent submits experience with `capture` (raw events, processed asynchronously) or `remember` (a direct fact). Both flow through the same pipeline: a cheap importance gate, LLM extraction + classification, deterministic validation, and **temporal reconciliation** against what is already known.

```mermaid
sequenceDiagram
  autonumber
  participant A as Agent
  participant API as FastAPI
  participant W as WriteService
  participant G as ImportanceGate
  participant Q as Qwen (extraction)
  participant R as Reconciler
  participant DB as PostgreSQL
  participant AGE as Apache AGE

  A->>API: capture(events) / remember(fact)
  API->>DB: persist immutable episode(s)
  API-->>A: 202 Accepted (job queued) / 201 Created

  Note over W,DB: worker picks up EXTRACT_EPISODE job
  W->>G: should_extract(text)?
  alt trivial (empty / 1–2 word ack, no marker)
    G-->>W: skip: no LLM call
  else durable content
    G-->>W: extract
    W->>Q: extract_memories(text, context)
    Q-->>W: candidates + classification (type, criticality)
    W->>W: deterministic guardrails (extraction_validation)
    loop each candidate
      W->>R: decide(candidate vs. existing active memory)
      R-->>W: ADD · REINFORCE · SUPERSEDE · CONTEST · NOOP
      W->>Q: embed(candidate)  %% text-embedding-v4, 1024-d
      W->>DB: write canonical memory version + search doc + embedding
      W->>DB: write graph claims (claims-first)
      W->>AGE: project accepted relations into temporal graph
    end
  end
```

**Importance gate** (`write/importance.py`): a recall-oriented pre-filter, not the precision layer. It only skips content that cannot hold durable knowledge (empty text, one- or two-word acknowledgements), while rescue markers like `always`, `never`, `must`, `use`, `prefer`, `decision`, `constraint` keep short imperatives ("use pnpm") in play. Everything else is handed to the LLM classifier to accept or reject.

**Reconciliation** (`learning/reconciliation.py`) is what makes memory temporal instead of append-only. Comparing a new candidate against the existing active memory yields one operation:

- **ADD**: no related memory exists yet.
- **REINFORCE**: same value again; adds evidence / confidence.
- **SUPERSEDE**: a newer value replaces an older one (driven by temporal cues like "used to", "now instead of", "no longer", "switched from", "corrected"). The old version is retained as `superseded`, never deleted.
- **CONTEST**: a conflicting value arrives; both sides stay retrievable, ranked below settled facts, until resolved.
- **NOOP**: provider marked the candidate as noise.

**Claims-first graph writes**: accepted relations are persisted in PostgreSQL (`graph_entities`, `graph_claims`) and then projected into the Apache AGE temporal graph. Graph edges are always projections of accepted memory versions, never written from raw episodes.

---

## The read path: recall under a context budget

`retrieve` takes a query, a **token budget**, an optional `task_type`, and a `limit`. It filters by scope and lifecycle, gathers candidates from up to five channels, fuses them, ranks by utility, **reserves budget for critical memories**, and packs the final context, writing a full retrieval trace for every decision.

```mermaid
flowchart TB
  Q[retrieve · query · token_budget · task_type] --> F{scope + lifecycle filter<br/>ACTIVE / CONTESTED · valid_from / valid_until}
  F --> C1[Critical lookup<br/>must_include]
  F --> C2[Structured match<br/>subject · key]
  F --> C3[Lexical FTS<br/>term overlap]
  F --> C4[Semantic<br/>pgvector cosine]
  F --> C5[Graph traversal<br/>Apache AGE · gated]

  C2 & C3 & C4 & C5 --> RRF[Reciprocal Rank Fusion<br/>k = 60]
  RRF --> RANK[Utility-aware ranking<br/>+ usefulness·0.12 + confidence·0.08<br/>+ scope specificity + task match<br/>− contested penalty]

  C1 --> RES[Reserve critical budget<br/>20% of tokens · ≤ 3 facts]
  RES --> PACK
  RANK --> PACK[Greedy token-budget packer<br/>critical first, then ranked]
  PACK --> CTX[Packed context]
  PACK --> TRACE[(Retrieval trace<br/>per-item scores + tokens)]
```

**Channels** (`read/retrieval.py`)

- **Critical lookup**: surfaces `must_include` constraints regardless of query overlap.
- **Structured match**: exact overlap on a memory's `subject`/`key` (great for identifiers).
- **Lexical**: full-text term overlap; exact recall for names, flags, versions.
- **Semantic**: cosine similarity over `text-embedding-v4` vectors in pgvector (per-channel cap of 50).
- **Graph**: Apache AGE traversal, only invoked when the query looks relational and the graph store is available; depth is clamped.

**Reciprocal Rank Fusion** (`RRF_K = 60`) combines the ranked channel outputs without needing to normalize incomparable score scales.

**Utility-aware ranking** adds signals on top of the fused score: `usefulness × 0.12`, `confidence × 0.08`, scope specificity (user/project-scoped memories rank higher), a `+0.05` task-type-match boost, and a `−0.04` penalty for contested memories.

**Critical reservation + packing** is the answer to "recall critical memories within a limited context window." Before normal results are packed, `_select_critical` reserves **20% of the token budget** (`token_budget × 0.2`) for up to **3** `must_include` memories, ranked by query relevance. The greedy packer then emits **critical first**, then ranked normal memories, stopping at the budget. So even at a tiny budget, the non-negotiable constraints make it into context.

Every retrieval persists a **trace** with each candidate's lexical/semantic/graph scores, usefulness, final rank, token count, and whether it was selected, the basis for both debugging and outcome learning.

---

## Forgetting: keeping memory sharp over time

Timely forgetting runs as the idempotent **`EXPIRE_MEMORIES`** background job (`learning/lifecycle.py`). Every step is safe to repeat and never physically deletes normal history.

```mermaid
flowchart LR
  J([EXPIRE_MEMORIES job]) --> E[Expire memories<br/>past valid_until]
  J --> D[Decay usefulness<br/>half-life 30d → neutral 0.5]
  J --> R[Resolve contested<br/>leader margin ≥ 0.15]
  J --> CE[Expire due<br/>graph claims + edges]
  D -.harmful drives ≤ 0.05.-> AR[Archive version]
```

- **Validity expiry**: memories with a `valid_until` in the past move to `expired` but remain queryable as history.
- **Usefulness decay**: usefulness relaxes toward the neutral `0.5` on a **30-day half-life**: `factor = 0.5 ^ (elapsed / half_life)`. A memory must keep earning its rank through use, or it quietly fades in the ranking. Rows touched within the last 24h are skipped so decay runs are cheap no-ops.
- **Contested resolution**: a contested pair settles once one side leads by a combined usefulness+confidence margin of `0.15`.
- **Harmful archival**: feedback that drives usefulness to `≤ 0.05` expires the version outright.
- **Graph hygiene**: due claims and projected edges expire alongside their memories.

The result: outdated facts stop winning retrieval **without** losing the audit trail of what the agent once believed and why it changed.

---

## Outcome learning

After using retrieved context, an agent reports an outcome via `feedback`: **helpful**, **unused**, or **harmful**. This adjusts the **usefulness score only** on the memories (and graph edges) involved. It **never** changes factual content, truth confidence, lifecycle status, or validity intervals. Over many sessions, memories that repeatedly help rise; those that mislead sink and can be archived, which is how decisions get "increasingly accurate" without corrupting stored truth.

---

## Memory lifecycle

```mermaid
stateDiagram-v2
  [*] --> candidate: extracted
  candidate --> active: promoted
  candidate --> [*]: rejected / NOOP
  active --> superseded: SUPERSEDE (newer value)
  active --> contested: CONTEST (conflict)
  active --> expired: valid_until passed / harmful
  contested --> active: resolved (margin ≥ 0.15)
  contested --> superseded: correction wins
  active --> deleted: explicit delete
  superseded --> [*]: retained as history
  expired --> [*]: retained as history
```

Statuses: `candidate → active → {superseded | contested | expired | deleted}`. Superseded and expired versions are **kept**, retrieval filters them out of live results but they remain for explanation and audit.

---

## Data model

PostgreSQL holds every durable fact:

- **Episodes**: immutable raw experience (`user_message`, `agent_message`, `tool_call`, `tool_result`, `user_feedback`, `task_result`, `environment_observation`).
- **Canonical memories**: versioned, typed (`preference`, `fact`, `decision`, `constraint`, `goal`, `lesson`), with criticality (`normal`, `high_priority`, `must_include`), usefulness, confidence, and validity intervals. Each version stores its embedding + a search document.
- **Graph**: `graph_entities` and `graph_claims` in PostgreSQL, projected into an Apache AGE temporal graph of typed relations.
- **Retrieval traces**: per-query, per-candidate scoring records.
- **Feedback**: outcome signals (`helpful`/`unused`/`harmful`) from `user`/`developer`/`tool`/`evaluator`/`agent`.
- **Jobs**: `extract_episode`, `consolidate_session`, `expire_memories`, `project_graph`, `rebuild_graph`.

---

## API & SDK surface

Agents integrate over HTTP or the generated TypeScript SDK (`memrise-memory-sdk`, fetch-based, no runtime deps). The core loop is a handful of calls:

| Call                | Endpoint                            | Purpose                                                              |
| ------------------- | ----------------------------------- | -------------------------------------------------------------------- |
| `capture`           | `POST /v1/episodes`                 | Submit raw events; extraction happens asynchronously (202).          |
| `remember`          | `POST /v1/memories`                 | Record a durable fact directly (201).                                |
| `retrieve`          | `POST /v1/memories/retrieve`        | Recall context under a token budget; returns packed context + trace. |
| `respond`           | `POST /v1/agent/respond`            | Retrieve + generate a memory-grounded answer with Qwen.              |
| `feedback`          | `POST /v1/retrievals/{id}/feedback` | Report a retrieval outcome (updates usefulness only).                |
| `consolidate`       | `POST /v1/sessions/.../consolidate` | Replay a session to consolidate durable knowledge.                   |
| `graphNeighborhood` | `GET /v1/graph/neighborhood`        | Fetch a query's entity/relation neighborhood for inspection.         |

Supporting endpoints cover memory explanation/versions, retrieval history, job status, lifecycle runs, and health. The OpenAPI spec (`contracts/openapi.json`) and SDK types (`packages/sdk-typescript/src/generated/api-types.ts`) are generated, refresh with `make generate-sdk`.

### TypeScript example

```ts
import { MemriseClient } from "memrise-memory-sdk";

const memory = new MemriseClient({
  baseUrl: process.env.MEMRISE_API_URL!,
  apiKey: process.env.MEMRISE_API_KEY!,
});

// 1. Accumulate experience
await memory.capture({
  namespaceId: "local",
  agentId: "coding-agent",
  sessionId: "session-1",
  userId: "user-1",
  projectId: "atlas",
  events: [{ kind: "user_message", content: "Atlas uses pnpm.", metadata: {} }],
});

// 2. Recall under a context budget
const context = await memory.retrieve({
  namespaceId: "local",
  agentId: "coding-agent",
  projectId: "atlas",
  query: "How should I install dependencies for Atlas?",
  tokenBudget: 800,
  limit: 10,
});
```

### Python example

```python
from memrise import Memrise

memory = Memrise.from_env()
await memory.capture(
    namespace_id="local",
    agent_id="coding-agent",
    session_id="session-1",
    user_id="user-1",
    project_id="atlas",
    events=[{"kind": "user_message", "content": "Atlas uses pnpm.", "metadata": {}}],
)
```

---

## Quick start

```bash
make bootstrap
docker compose -f infra/compose.yaml up -d postgres
make migrate
make dev
```

Set `ALIBABA_CLOUD_API_KEY` (see `.env.example`) so the Qwen adapter can extract, embed, retrieve, and answer.

- **API**: `http://localhost:8000`
- **Inspector**: `http://localhost:3000` (a live console that runs capture → retrieve → learn and renders the knowledge graph as it grows)

---

## Repository map

- `packages/engine`: Python core: `core/` (dataclasses, enums), `ports/` (protocols), `write/`, `read/`, `learning/`, `graph/`, `consolidation/`, `integrations/` (PostgreSQL + Qwen), `runtime/` (composition root), Alembic migrations.
- `apps/api`: FastAPI HTTP layer (validation, auth, DI, error translation).
- `apps/worker`: PostgreSQL-backed background job runner.
- `packages/sdk-typescript` (`memrise-memory-sdk`): fetch-based SDK generated from OpenAPI.
- `apps/web`: Next.js inspector with a live memory console and force-directed knowledge graph.
- `docs`: architecture diagrams and design references.
- `infra`: Docker Compose stack, Dockerfiles, PostgreSQL extension bootstrap.
- `contracts`: generated OpenAPI spec.

---

## Development

`make bootstrap` installs dependencies and points Git at `.githooks/`. See [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md) for boundaries and conventions.

- `make format`: Ruff + Prettier.
- `make check`: static checks and unit/contract tests.
- `make test-integration`: after PostgreSQL is up and migrated.
- `make generate-sdk`: refresh `contracts/openapi.json` and the SDK types.

Pre-commit hooks run staged-file-aware Ruff, Prettier, ESLint/typecheck, and Pyright, plus a legacy-name scan; the commit-msg hook enforces Conventional Commit subjects.

---

## Current limitations

- Consolidation replays session extraction today; fuller merge/compress/resolve steps are planned, not yet wired.
- Capture, remember, retrieve, and respond require a configured Qwen API key, there is no in-app model fallback.
- Qwen prompts are initial versions and need eval-driven refinement.
- Authorization is a simple API key, intentionally not production-grade multi-tenant auth.
- The inspector is a data-inspection tool, not a polished product UI.

MIT License.
