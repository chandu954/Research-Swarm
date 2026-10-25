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
    status: number;
    constructor(message: string, status: number) {
      super(message);
      this.name = "ApiClientError";
      this.status = status;
    }
  },
}));

import { api } from "@/lib/api-client";

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

describe("AuthProvider", () => {
  it("login stores tokens and fetches user", async () => {
    mockPost.mockResolvedValue(tokenPair);
    renderProvider(<Consumer />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "login" }));
    });
    expect(mockPost).toHaveBeenCalledWith(
      "/auth/login",
      { email: "a@b.com", password: "password123" },
      { retryable: false },
    );
    expect(localStorage.getItem("research-swarm-token")).toBe("access-1");
    expect(localStorage.getItem("research-swarm-refresh")).toBe("refresh-1");
    expect(screen.getByTestId("user")).toHaveTextContent("User");
  });

  it("register stores tokens", async () => {
    mockPost.mockResolvedValue(tokenPair);
    renderProvider(<Consumer />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "register" }));
    });
    expect(mockPost).toHaveBeenCalledWith(
      "/auth/register",
      { email: "a@b.com", password: "password123", name: "User" },
      { retryable: false },
    );
    expect(localStorage.getItem("research-swarm-token")).toBe("access-1");
  });

  it("logout clears tokens and user", async () => {
    mockPost.mockResolvedValue(tokenPair);
    renderProvider(<Consumer />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "login" }));
    });
    expect(localStorage.getItem("research-swarm-token")).toBe("access-1");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "logout" }));
    });
    expect(localStorage.getItem("research-swarm-token")).toBeNull();
    expect(screen.getByTestId("user")).toHaveTextContent("");
  });

  it("refresh returns false when no refresh token", async () => {
    renderProvider(<Consumer />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "refresh" }));
    });
    // No refresh token stored => refresh exits early without calling the API.
    expect(mockPost).not.toHaveBeenCalled();
    expect(localStorage.getItem("research-swarm-token")).toBeNull();
  });

  it("refresh rotates tokens on success", async () => {
    localStorage.setItem("research-swarm-refresh", "refresh-1");
    mockPost.mockResolvedValue(tokenPair);
    renderProvider(<Consumer />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "refresh" }));
    });
    expect(mockPost).toHaveBeenCalledWith(
      "/auth/refresh",
      { refresh_token: "refresh-1" },
      { retryable: false },
    );
    expect(localStorage.getItem("research-swarm-token")).toBe("access-1");
  });
});
