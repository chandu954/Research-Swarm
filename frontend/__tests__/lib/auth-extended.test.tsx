import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, fireEvent } from "@testing-library/react";
import { AuthProvider, useAuth } from "@/lib/auth";

const { mockPost, mockGet } = vi.hoisted(() => ({
  mockPost: vi.fn(),
  mockGet: vi.fn(),
}));

vi.mock("@/lib/api-client", () => ({
  api: { post: mockPost, get: mockGet },
  TOKEN_KEY: "research-swarm-token",
  REFRESH_KEY: "research-swarm-refresh",
  ApiClientError: class ApiClientError extends Error {
    code: string;
    status: number;
    retryable: boolean;
    constructor(message: string, code: string, status: number, retryable: boolean) {
      super(message);
      this.name = "ApiError";
      this.code = code;
      this.status = status;
      this.retryable = retryable;
    }
  },
}));

import { api, ApiClientError } from "@/lib/api-client";

const tokenPair = {
  access_token: "access-1",
  refresh_token: "refresh-1",
  supabase_access_token: "sb-access",
  supabase_refresh_token: "sb-refresh",
};

const authUser = {
  id: "user-1",
  email: "user@example.com",
  name: "User",
  avatar_url: null,
  is_active: true,
  mfa_enabled: false,
};

function Consumer() {
  const { login, register, logout, refreshToken } = useAuth();
  return (
    <div>
      <span data-testid="user">{useAuth().user?.name ?? ""}</span>
      <button onClick={() => login("a@b.com", "password123")}>login</button>
      <button onClick={() => register("a@b.com", "password123", "User")}>
        register
      </button>
      <button onClick={logout}>logout</button>
      <button onClick={refreshToken}>refresh</button>
    </div>
  );
}

function OAuthConsumer() {
  const { oauthLogin } = useAuth();
  return <button onClick={() => void oauthLogin("google")}>oauth</button>;
}

function renderProvider(ui: React.ReactElement) {
  return render(<AuthProvider>{ui}</AuthProvider>);
}

beforeEach(() => {
  localStorage.clear();
  vi.resetAllMocks();
  mockGet.mockResolvedValue(authUser);
});

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe("AuthProvider extended", () => {
  it("fetchUser clears auth on 401 from /auth/me", async () => {
    mockGet.mockRejectedValueOnce(new ApiClientError("Unauthorized", "UNAUTHORIZED", 401, false));
    localStorage.setItem("research-swarm-token", "stale-token");
    renderProvider(<Consumer />);
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    expect(localStorage.getItem("research-swarm-token")).toBeNull();
    expect(screen.getByTestId("user")).toHaveTextContent("");
  });

  it("refreshToken clears auth on API failure", async () => {
    localStorage.setItem("research-swarm-refresh", "refresh-1");
    localStorage.setItem("research-swarm-token", "old-token");
    mockPost.mockRejectedValue(new Error("refresh failed"));
    renderProvider(<Consumer />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "refresh" }));
      await new Promise((r) => setTimeout(r, 50));
    });
    expect(localStorage.getItem("research-swarm-token")).toBeNull();
    expect(screen.getByTestId("user")).toHaveTextContent("");
  });

  it("oauthLogin calls window.open with oauth url", async () => {
    const fakePopup = { closed: false } as unknown as Window;
    const openSpy = vi.spyOn(window, "open").mockReturnValue(fakePopup);
    renderProvider(<OAuthConsumer />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "oauth" }));
      await new Promise((r) => setTimeout(r, 100));
    });
    expect(openSpy).toHaveBeenCalledWith(
      expect.stringContaining("/auth/google"),
      "googleOAuth",
      expect.any(String),
    );
    openSpy.mockRestore();
  });

  it("useAuth throws outside AuthProvider", () => {
    function Throws() {
      return <div>{useAuth().user?.name ?? "none"}</div>;
    }
    expect(() => render(<Throws />)).toThrow(
      "useAuth must be used within AuthProvider",
    );
  });
});
