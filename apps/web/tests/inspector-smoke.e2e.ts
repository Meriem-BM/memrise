import { expect, test } from "@playwright/test";

test("console runs a full agent turn", async ({ page }) => {
  await page.route("**/v1/agent/respond", async (route) => {
    const request = route.request().postDataJSON() as { query: string; use_memory?: boolean };
    if (request.use_memory === false) {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          answer: "I do not know from this turn alone.",
          model_name: "qwen3.6-flash",
          prompt_version: "agent_answer_v1",
          memory_enabled: false,
          retrieval: null,
        }),
      });
      return;
    }
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({
        answer: "Atlas uses pnpm for dependencies.",
        model_name: "qwen3.6-flash",
        prompt_version: "agent_answer_v1",
        memory_enabled: true,
        retrieval: {
          retrieval_id: "retrieval_1",
          query: request.query,
          token_budget: 800,
          used_tokens: 9,
          critical: [],
          memories: [
            {
              memory_id: "mem_1",
              memory_version_id: "memv_1",
              type: "decision",
              subject: "Atlas",
              key: "package_manager",
              content: "Atlas uses pnpm for dependencies.",
              status: "active",
              criticality: "normal",
              confidence: 0.9,
              importance: 0.7,
              usefulness_score: 0.5,
              token_count: 9,
              source_types: [],
              selected_for_context: true,
              provenance_episode_ids: [],
              explanation: {},
            },
          ],
          context: "- Atlas uses pnpm for dependencies.",
        },
      }),
    });
  });
  await page.route("**/v1/retrievals/retrieval_1", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        retrieval_id: "retrieval_1",
        items: [
          {
            retrieval_id: "retrieval_1",
            memory_version_id: "memv_1",
            graph_edge_id: null,
            source_type: "lexical",
            original_rank: 1,
            final_rank: 1,
            lexical_score: 0.8,
            semantic_score: 0.6,
            graph_score: null,
            usefulness_score: 0.5,
            selected_for_context: true,
            token_count: 9,
          },
        ],
      }),
    });
  });
  await page.route("**/v1/episodes", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({ episode_ids: ["ep_1"], job_ids: ["job_1"] }),
      });
      return;
    }
    await route.fallback();
  });
  await page.route("**/v1/jobs/job_1", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "job_1",
        type: "extract_episode",
        status: "completed",
        attempts: 1,
        max_attempts: 3,
        run_at: "2026-07-04T00:00:00Z",
        locked_at: null,
        locked_by: null,
        last_error: null,
        created_at: "2026-07-04T00:00:00Z",
        updated_at: "2026-07-04T00:00:00Z",
      }),
    });
  });
  await page.route("**/v1/episodes/ep_1/candidates", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: "cand_1",
          episode_id: "ep_1",
          candidate_index: 0,
          status: "promoted",
          promotion_score: 0.81,
          rejection_reason: null,
          memory_id: "mem_1",
          memory_version_id: "memv_1",
          memory_type: "decision",
          subject: "Atlas",
          key: "package_manager",
          evidence_quote: "we now use pnpm",
          classification: { durability: "durable", sensitivity: "normal" },
          created_at: "2026-07-04T00:00:00Z",
        },
      ]),
    });
  });
  await page.route("**/v1/graph/neighborhood**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ nodes: [], edges: [] }),
    });
  });

  await page.goto("/console");
  await expect(page.getByRole("switch", { name: "Deactivate Memrise" })).toBeVisible();
  await page.getByPlaceholder("talk to the memory…").fill("we now use pnpm instead of npm");
  await page.keyboard.press("Enter");

  await expect(
    page.getByText("answered with Memrise · recalled 1 · learned Atlas · package_manager"),
  ).toBeVisible();
  await expect(page.getByText("Memrise on").first()).toBeVisible();
  await expect(page.getByText("Atlas uses pnpm for dependencies.").first()).toBeVisible();
  await expect(page.getByText("qwen3.6-flash · agent_answer_v1 · Memrise on")).toBeVisible();
  await expect(page.getByText("lexical")).toBeVisible();
  await expect(
    page.getByText(
      "Showing memory-derived relations while the projected knowledge graph is empty.",
    ),
  ).toBeVisible();
  await expect(page.locator(".react-flow__edge-text").filter({ hasText: /^USES$/ })).toBeVisible();

  await page.getByRole("switch", { name: "Deactivate Memrise" }).click();
  await expect(page.getByRole("switch", { name: "Activate Memrise" })).toBeVisible();
  await page.getByPlaceholder("talk to the memory…").fill("what package manager does Atlas use?");
  await page.keyboard.press("Enter");

  await expect(
    page.getByText("answered without Memrise · recall off · extraction skipped"),
  ).toBeVisible();
  await expect(page.getByText("I do not know from this turn alone.").first()).toBeVisible();
  await expect(page.getByText("Memrise off").first()).toBeVisible();
});

test("sdk page shows quickstart snippets", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText("Give your agent a memory.")).toBeVisible();
  await expect(page.getByText("pnpm add memrise-memory-sdk")).toBeVisible();
  await expect(page.getByText("Recall — retrieve context")).toBeVisible();
});
