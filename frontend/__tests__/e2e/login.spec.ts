import { test, expect } from "@playwright/test";
import { mockExternalServices } from "./mocks";

test.describe("Login flow", () => {
  test.beforeEach(async ({ page }) => mockExternalServices(page));

  test("shows login page", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByText("Welcome back to ResearchSwarm")).toBeVisible();
  });

  test("redirects to login when unauthenticated", async ({ page }) => {
    await page.goto("/app");
    await expect(page).toHaveURL(/\/login/);
  });

  test("shows validation errors", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/email address/i).fill("reader@example.test");
    await page.getByLabel("Password *").fill("short");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page.getByRole("alert").filter({ hasText: /at least 8 characters/i })).toBeVisible();
  });
});
