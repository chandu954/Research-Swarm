import type { Page, Route } from "@playwright/test";

const researchResult = {
  task_id: "e2e-task",
  query: "Explain deterministic tests",
  answer: "A deterministic test uses controlled inputs and predictable outcomes.",
  sources: [],
  plan: [],
  logs: [],
  status: "completed",
  errors: [],
  execution_time: 0.1,
};

async function mockExternalRequest(route: Route) {
  const url = new URL(route.request().url());
  if (url.port === "3001" && ["localhost", "127.0.0.1"].includes(url.hostname)) {
    await route.continue();
    return;
  }

  if (url.pathname === "/health") {
    await route.fulfill({ json: { status: "ok" } });
  } else if (url.pathname === "/auth/org-status") {
    await route.fulfill({ json: { has_organization: true } });
  } else if (url.pathname === "/auth/me") {
    await route.fulfill({
      json: { id: "e2e-user", email: "e2e@example.test", name: "E2E User" },
    });
  } else if (url.pathname === "/organizations") {
    await route.fulfill({
      json: [{ id: "org-1", name: "Test Org", slug: "test-org", owner_id: "e2e-user", member_count: 1 }],
    });
  } else if (url.pathname === "/organizations/org-1/workspaces") {
    await route.fulfill({
      json: [{ id: "ws-1", name: "Test Workspace", slug: "test-workspace", organization_id: "org-1", owner_id: "e2e-user", member_count: 1, is_active: true }],
    });
  } else if (url.pathname === "/organizations/org-1/workspaces/ws-1/projects") {
    await route.fulfill({ json: [] });
  } else if (url.pathname.startsWith("/research/stream/")) {
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: "event: done\ndata: {}\n\n",
    });
  } else if (url.pathname === "/research") {
    await route.fulfill({ json: researchResult });
  } else {
    await route.fulfill({ json: [] });
  }
}

export async function mockExternalServices(page: Page) {
  // Requests to the test server continue; every other network request is
  // served from deterministic fixtures so E2E runs cannot reach live services.
  await page.route("**/*", mockExternalRequest);
}

export async function establishTestSession(page: Page) {
  await page.goto("/login");
  const token = `e30.${Buffer.from(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 })).toString("base64url")}.c2ln`;
  await page.context().addCookies([
    { name: "research-swarm-token", value: token, url: new URL(page.url()).origin },
  ]);
  await page.evaluate((storedToken) => {
    localStorage.setItem("research-swarm-token", storedToken);
  }, token);
}
