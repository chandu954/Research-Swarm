import { test, expect } from "@playwright/test";
import { establishTestSession, mockExternalServices } from "./mocks";

test.describe("Research flow", () => {
  test.beforeEach(async ({ page }) => {
    await mockExternalServices(page);
    await establishTestSession(page);
  });

  test("loads the research workspace", async ({ page }) => {
    await page.goto("/app");
    await expect(page.getByRole("textbox", { name: "Research question" })).toBeVisible();
  });

  test("shows settings panel", async ({ page }) => {
    await page.goto("/app");
    await page.getByRole("button", { name: /settings/i }).click();
    await expect(page.getByText(/llm provider/i)).toBeVisible();
  });

  test("submits research and renders the answer", async ({ page }) => {
    await page.goto("/app");
    await page.getByRole("textbox", { name: "Research question" }).fill("Explain deterministic tests");
    await page.getByRole("button", { name: "Start research", exact: true }).click();
    await expect(page.getByText(/A deterministic test uses controlled inputs/)).toBeVisible();
  });
});
