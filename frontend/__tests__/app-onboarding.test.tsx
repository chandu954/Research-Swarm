import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ push: vi.fn(), token: "jwt-test-token" }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ token: mocks.token }) }));
vi.mock("@/lib/config", () => ({ getApiUrl: () => "http://api.test" }));

import OnboardingPage from "@/app/onboarding/page";

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  vi.stubGlobal("fetch", vi.fn());
});

async function openOrganizationStep() {
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));
  await screen.findByText("Create your organization");
}

describe("OnboardingPage", () => {
  it("normalizes the organization slug and sends the authenticated request", async () => {
    render(<OnboardingPage />);
    await openOrganizationStep();
    fireEvent.change(screen.getByPlaceholderText("e.g. Acme Corp"), {
      target: { value: "  Research & Development!  " },
    });
    expect(screen.getByPlaceholderText("acme-corp")).toHaveValue("research-development");

    vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify({ id: "org-1" }), { status: 201 }));
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() => expect(localStorage.getItem("research-swarm-org-id")).toBe("org-1"));
    expect(fetch).toHaveBeenCalledWith("http://api.test/organizations", expect.objectContaining({
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer jwt-test-token" },
      body: JSON.stringify({ name: "Research & Development!", slug: "research-development" }),
    }));
  });

  it("shows API errors and stays on the organization step", async () => {
    render(<OnboardingPage />);
    await openOrganizationStep();
    fireEvent.change(screen.getByPlaceholderText("e.g. Acme Corp"), { target: { value: "Research" } });
    vi.mocked(fetch).mockResolvedValueOnce(new Response(
      JSON.stringify({ detail: "Organization name already exists" }),
      { status: 409, headers: { "Content-Type": "application/json" } },
    ));
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    expect(await screen.findByText("Organization name already exists")).toBeInTheDocument();
    expect(screen.getByText("Create your organization")).toBeInTheDocument();
    expect(localStorage.getItem("research-swarm-org-id")).toBeNull();
  });

  it("creates workspace and project with parent ids, then enters the app", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "org-1" }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "ws-1" }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "project-1" }), { status: 201 }));
    render(<OnboardingPage />);
    await openOrganizationStep();
    fireEvent.change(screen.getByPlaceholderText("e.g. Acme Corp"), { target: { value: "Acme" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(localStorage.getItem("research-swarm-org-id")).toBe("org-1"));

    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(localStorage.getItem("research-swarm-ws-id")).toBe("ws-1"));
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(localStorage.getItem("research-swarm-project-id")).toBe("project-1"));
    fireEvent.click(screen.getByRole("button", { name: /go to workspace/i }));

    expect(mocks.push).toHaveBeenCalledWith("/app");
    expect(fetch).toHaveBeenNthCalledWith(2, "http://api.test/organizations/org-1/workspaces", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ name: "General", slug: "general" }),
    }));
    expect(fetch).toHaveBeenNthCalledWith(3, "http://api.test/organizations/org-1/workspaces/ws-1/projects", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ name: "Default Project", slug: "default" }),
    }));
  });
});
