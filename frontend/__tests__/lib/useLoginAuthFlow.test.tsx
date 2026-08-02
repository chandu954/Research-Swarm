import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useLoginAuthFlow } from "@/lib/useLoginAuthFlow";

const mockPush = vi.fn();
const mockLogin = vi.fn();
const mockRegister = vi.fn();
const mockOauthLogin = vi.fn();
const mockCheckHealth = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    login: mockLogin,
    register: mockRegister,
    oauthLogin: mockOauthLogin,
  }),
}));

vi.mock("@/lib/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api-client")>();
  return {
    ...actual,
    checkHealth: (...args: unknown[]) => mockCheckHealth(...args),
  };
});

describe("useLoginAuthFlow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    mockCheckHealth.mockResolvedValue({ ok: true, status: "healthy" });
    Object.defineProperty(navigator, "onLine", { value: true, writable: true, configurable: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("starts with checking_backend then becomes idle when healthy", async () => {
    const { result } = renderHook(() => useLoginAuthFlow());
    expect(result.current.state.status).toBe("checking_backend");

    await waitFor(() => {
      expect(result.current.state.status).toBe("idle");
    });
    expect(result.current.isBlocked).toBe(false);
  });

  it("blocks auth when backend is unhealthy", async () => {
    mockCheckHealth.mockResolvedValue({ ok: false, status: "offline" });
    const { result } = renderHook(() => useLoginAuthFlow());

    await waitFor(() => {
      expect(result.current.state.status).toBe("backend_offline");
    });
    expect(result.current.isBlocked).toBe(true);
    expect(result.current.banner?.kind).toBe("backend_offline");
  });

  it("transitions to authentication_success on login and redirects once", async () => {
    mockLogin.mockResolvedValue(undefined);
    const { result } = renderHook(() => useLoginAuthFlow());

    await waitFor(() => expect(result.current.state.status).toBe("idle"));

    await act(async () => {
      await result.current.performLogin("user@test.com", "password123");
    });

    expect(["authentication_success", "redirecting"]).toContain(result.current.state.status);
    expect(result.current.banner?.kind).toBe("success");
    expect(result.current.banner?.kind).not.toBe("backend_offline");

    await waitFor(
      () => expect(mockPush).toHaveBeenCalledWith("/app"),
      { timeout: 2000 },
    );
    expect(mockPush).toHaveBeenCalledTimes(1);
  });

  it("shows authentication_failed on wrong password without backend_offline", async () => {
    const { ApiError } = await import("@/lib/api-client");
    mockLogin.mockRejectedValue(new ApiError("Unauthorized", "UNAUTHORIZED", 401, false));
    const { result } = renderHook(() => useLoginAuthFlow());

    await waitFor(() => expect(result.current.state.status).toBe("idle"));

    await act(async () => {
      try {
        await result.current.performLogin("user@test.com", "wrong");
      } catch { /* expected */ }
    });

    expect(result.current.state.status).toBe("authentication_failed");
    expect(result.current.banner?.kind).toBe("error");
    expect(result.current.banner?.kind).not.toBe("backend_offline");
  });

  it("prevents double-click login via submit lock", async () => {
    mockLogin.mockResolvedValue(undefined);
    const { result } = renderHook(() => useLoginAuthFlow());
    await waitFor(() => expect(result.current.state.status).toBe("idle"));

    await act(async () => {
      void result.current.performLogin("a@b.com", "password123");
      void result.current.performLogin("a@b.com", "password123");
    });

    expect(mockLogin).toHaveBeenCalledTimes(1);
  });

  it("handles OAuth failure as oauth_failed", async () => {
    mockOauthLogin.mockRejectedValue(new DOMException("Popup closed", "AbortError"));
    const { result } = renderHook(() => useLoginAuthFlow());
    await waitFor(() => expect(result.current?.state.status).toBe("idle"));

    await act(async () => {
      await result.current.performOAuth("google");
    });

    expect(result.current.state.status).toBe("oauth_failed");
    expect(result.current.banner?.kind).toBe("error");
  });

  it("freezes success banner after AUTH_SUCCESS even if health check is unhealthy", async () => {
    mockLogin.mockResolvedValue(undefined);
    mockCheckHealth.mockResolvedValue({ ok: true, status: "healthy" });

    const { result } = renderHook(() => useLoginAuthFlow());

    await waitFor(() => expect(result.current.state.status).toBe("idle"));

    await act(async () => {
      await result.current.performLogin("user@test.com", "password123");
    });

    expect(result.current.banner?.kind).toBe("success");

    // Simulate backend health flipping to unhealthy immediately after success.
    mockCheckHealth.mockResolvedValue({ ok: false, status: "offline" });

    // Trigger the hook's runHealthCheck via online/offline events (immediate, no interval).
    act(() => {
      window.dispatchEvent(new Event("offline"));
    });

    // Let effects/state settle.
    await waitFor(() => {
      // banner must remain success due to freeze logic
      expect(result.current.banner?.kind).toBe("success");
      expect(result.current.banner?.kind).not.toBe("backend_offline");
    });
  });
});
