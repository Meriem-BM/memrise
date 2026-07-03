# Web Inspector Redesign — Design

**Date:** 2026-07-03
**Status:** Approved
**Approach:** C — new workflow-shaped IA, reused UI foundation, five shippable phases.

## Problem

The web app hides everything interesting about the engine. The playground dumps
raw JSON; candidate staging (with rejection reason codes), reconciliation
decisions, ranking channels, contested pairs, and lifecycle events are all
invisible; the status page is placeholder-grade; the graph page hardcodes its
query; testing is single-shot capture/retrieve.

Audience: the developer debugging the engine first, demo viewers second. The
mechanism serving both is progressive disclosure — every screen reads as a
story collapsed and as an instrument expanded.

## Goals

- Expose every pipeline decision the engine already records.
- Make multi-turn, conflict, and lifecycle behavior testable from the browser.
- Give the Overview page real numbers (funnel, health, activity).
- Document SDK usage next to a working flow.

Non-goals: visual redesign (keep black/Inter/monochrome and the existing
card/badge/button kit), auth/multi-tenant UI, editing memories from the UI.

## 1. New API surface

All read-only except the lifecycle trigger. Thin routes over existing engine
capabilities; regenerate `contracts/openapi.json` and the TS SDK afterward.

| Endpoint                                            | Returns                                                                                                                                 | Engine work                                           |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| `GET /v1/episodes?namespace_id&agent_id&session_id` | Episode summaries (id, kind, content, created_at) for one session                                                                       | none — `list_session_episodes` exists                 |
| `GET /v1/episodes/{episode_id}/candidates`          | Candidate stages: status, promotion_score, rejection_reason, classification, memory_version_id                                          | none — `list_candidate_stages_for_episode` exists     |
| `GET /v1/memories?status=`                          | Existing list endpoint gains optional `status` filter (notably `contested`)                                                             | small store-level filter                              |
| `GET /v1/stats?namespace_id&agent_id&project_id`    | Funnel + health: episode count, candidate stages by status, top rejection reasons, memories by status, entity count, active claim count | new count queries + `Memrise.stats()`                 |
| `POST /v1/lifecycle/run`                            | `LifecycleResult` counts (expired versions/claims/edges, decayed, resolved contested)                                                   | expose existing `LifecycleService.run()` on `Memrise` |

Notes:

- New response schemas: `EpisodeSummary`, `CandidateStageSummary`,
  `InspectorStats`, `LifecycleRunResponse`. All `extra="forbid"` pydantic
  models in `memrise/schemas/responses.py`.
- Stats queries are simple GROUP BY counts scoped to namespace+agent; no
  caching needed at inspector scale.
- Lifecycle trigger runs inline (not via job queue) and returns the result so
  the Lab can render it immediately. It is idempotent by design.

## 2. Information architecture

Nav: **Overview (/) · Sessions (/sessions) · Retrieve (/retrieve) · Memories
(/memories) · Lab (/lab) · Graph (/graph) · SDK (/sdk)**.

- `/playground` is removed in Phase 1 (replaced by Sessions). `/retrievals`
  stays until Phase 4, when its trace list moves into Overview's activity feed
  and the route is removed; retrieval detail stays reachable from Retrieve
  results. Unlaunched app: no redirects needed.
- Memory detail (`/memories/[id]`) unchanged, but gains a PipelineTrace of its
  version history (reconciliation story) in a later phase if cheap.

## 3. Shared components (`apps/web/components/trace/`)

- `PipelineTrace` — ordered steps; each step: icon, label, decision badge,
  optional `ReasonBadge`, expandable raw-detail block (`<details>`-style).
  Collapsed shows only labels + decisions.
- `ReasonBadge` — maps engine reason codes to short human text via a
  dictionary (`candidate:low_confidence` → "confidence below 0.35"). Unknown
  codes render verbatim in mono.
- `ScoreBar` — horizontal 0–1 bar with mono label and value, used for channel
  scores and promotion scores.

These are presentation-only; data mapping lives in `apps/web/lib/trace.ts`
(pure functions, vitest-covered).

## 4. Sessions page (Phase 1)

Replaces Playground.

- Header: generated `session_id` (short readable slug), "New session" button,
  message-kind selector (`user_message` default, `agent_message`,
  `environment_observation`).
- Composer sends via `client.capture`; message appears in a chat-like column
  with a status spinner while jobs run (`waitForJob`).
- Per message, after extraction completes: fetch
  `GET /v1/episodes/{id}/candidates` and render a PipelineTrace:
  1. Gate — passed / skipped (from `job_ids` empty = skipped).
  2. Classification — durability, sensitivity, should_extract.
  3. One step per candidate — accepted (link to memory, promotion score bar)
     or rejected (ReasonBadge).
- "Consolidate session" button → `client.consolidate` + `waitForJob` → then
  re-list session candidates/memories and render what changed (new/reinforced
  memories since consolidation started).
- Session state is client-side only (React state); refreshing starts a new
  session but old sessions remain queryable by pasting a session id.

## 5. Retrieve page (Phase 2)

Replaces the retrieval JSON dump.

- Controls: query, task_type (free text), token_budget (number, default 800),
  limit. Submit → `client.retrieve`.
- After the response, fetch `GET /v1/retrievals/{retrieval_id}` for per-item
  channel scores.
- Render: critical memories section (if any), then ranked cards: content,
  subject/key/type badges, ScoreBars for lexical/semantic/graph, token count,
  "in context" marker for `selected_for_context`.
- Budget gauge: `used_tokens / token_budget`.
- Per-card feedback: Helpful / Harmful buttons →
  `client.feedback(retrievalId, {memoryVersionId, outcome, source: "developer"})`;
  show returned usefulness score inline.
- Raw JSON of the full response behind a collapsed toggle.

## 6. Lab page (Phase 3)

Scenario cards driving the real API. Every run generates a unique subject
suffix (`atlas-<slug>`) so reruns never collide with prior state.

1. **Correction → Supersede** — capture fact, wait; capture explicit
   correction; show memory history (v1 superseded, v2 active).
2. **Paraphrase → Reinforce** — capture the same fact twice in different
   words; show a single memory whose usefulness/confidence rose.
3. **Contested pair** — capture two conflicting statements without correction
   markers; show both contested; then "resolve": send helpful feedback to one
   side and run the lifecycle sweep; show winner active / loser superseded.
4. **Secret rejection** — capture text containing a fake API key; show the
   classification rejection.
5. **Lifecycle sweep** — standalone button → `POST /v1/lifecycle/run` → render
   result counts.

Each scenario renders its steps as a PipelineTrace and surfaces API errors as
failed steps rather than toasts. Scenarios are sequential API calls in a
client-side runner (`apps/web/features/lab/scenarios.ts`) — data-driven so new
scenarios are additions to a list, not new components.

## 7. Overview page (Phase 4)

Replaces Status.

- **Funnel card** — episodes → candidates staged → promoted / rejected, with a
  horizontal breakdown of top rejection reasons (from `/v1/stats`).
- **Memory health card** — status distribution (active/contested/expired/
  superseded), entity + active claim counts.
- **Activity card** — most recent retrieval traces (existing
  `GET /v1/retrievals`) and newest memories, interleaved by time.
- **Service card** — kept as is.

## 8. SDK page (Phase 5)

Static content page (`/sdk`): install (`pnpm add memrise-memory-sdk`), client
init for both modes (browser behind the `/api/memrise` proxy — no key — and
server-side with `apiKey`), then capture / retrieve / feedback / consolidate
snippets in TypeScript and curl, matching what Sessions/Retrieve actually do.
Copy button per block. Link to `/openapi.json`. Content lives as typed
constants in `apps/web/features/sdk/snippets.ts` so it's greppable and
lintable, not markdown files.

## Error handling

- New API routes reuse the error middleware; invalid params → 422.
- Web: every query/mutation renders its error inline in the owning card (the
  existing pattern); Lab renders errors as failed trace steps.
- `waitForJob` timeouts render as a "still running" trace step with the job id.

## Testing

- **API**: pytest per new endpoint (happy path + 404/validation), using the
  existing stub-backed conftest; contract test regenerated.
- **Engine**: unit tests for the new stats queries and `Memrise.stats()`/
  `run_lifecycle()` against `MemoryStoreStub` (stub gains matching count
  methods mirroring the PG queries).
- **SDK**: regenerated types; client tests for the new methods' body/query
  mapping.
- **Web**: vitest for `lib/trace.ts` mappers and the reason-code dictionary;
  Playwright smoke extended to visit all seven tabs and run one Lab scenario
  against the stubbed backend (existing e2e infra).

## Phases

| Phase | Ships                                         | New endpoints                         |
| ----- | --------------------------------------------- | ------------------------------------- |
| 1     | Sessions page + trace components + nav rename | episodes list, episode candidates     |
| 2     | Retrieve page                                 | none                                  |
| 3     | Lab page                                      | lifecycle run, memories status filter |
| 4     | Overview page                                 | stats                                 |
| 5     | SDK page                                      | none                                  |

Each phase ends green: ruff/pyright/pytest, contract+SDK regen when the API
changed, web typecheck/lint/test.
