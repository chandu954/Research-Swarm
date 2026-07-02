import { test, expect } from "@playwright/test";

test.describe("Research flow", () => {
  test.beforeEach(async ({ page }) => {
    // Mock auth for E2E testing
    await page.goto("/login");
    await page.evaluate(() => {
      localStorage.setItem("research-swarm-token", "test-token");
    });
  });

  test("loads the research workspace", async ({ page }) => {
    await page.goto("/app");
    await expect(page.getByPlaceholder(/ask/i)).toBeVisible();
  });

  test("shows settings panel", async ({ page }) => {
    await page.goto("/app");
    await page.getByRole("button", { name: /settings/i }).click();
    await expect(page.getByText(/llm provider/i)).toBeVisible();
  });
});
