import { expect, test } from "@playwright/test";

test("dashboard renders service health and memory counts", async ({ page }) => {
  await page.route("**/health/ready", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ status: "ok", database: "ok" }),
    });
  });
  await page.route("**/v1/memories?**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([
        { status: "active", criticality: "high_priority" },
        { status: "active", criticality: "must_include" },
      ]),
    });
  });

  await page.goto("/");

  await expect(page.getByText("Service")).toBeVisible();
  await expect(page.getByText("ok").first()).toBeVisible();
  await expect(page.getByText("critical")).toBeVisible();
});
