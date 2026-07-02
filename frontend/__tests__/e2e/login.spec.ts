import { test, expect } from "@playwright/test";

test.describe("Login flow", () => {
  test("shows login page", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: /sign in/i })).toBeVisible();
  });

  test("redirects to login when unauthenticated", async ({ page }) => {
    await page.goto("/app");
    await expect(page).toHaveURL(/\/login/);
  });

  test("shows validation errors", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page.getByText(/email/i)).toBeVisible();
  });
});
