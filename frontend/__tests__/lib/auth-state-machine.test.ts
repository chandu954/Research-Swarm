import { describe, it, expect } from "vitest";
import {
  authFlowReducer,
  INITIAL_AUTH_FLOW_STATE,
  getAuthBanner,
  isAuthInteractive,
  isAuthBlocked,
  isSubmitting,
  type AuthFlowState,
} from "@/lib/auth-state-machine";

describe("authFlowReducer", () => {
  it("starts in checking_backend", () => {
    expect(INITIAL_AUTH_FLOW_STATE.status).toBe("checking_backend");
  });

  it("transitions checking_backend → idle on BACKEND_HEALTHY", () => {
    const next = authFlowReducer(INITIAL_AUTH_FLOW_STATE, { type: "BACKEND_HEALTHY" });
    expect(next.status).toBe("idle");
  });

  it("transitions checking_backend → backend_offline on BACKEND_UNHEALTHY", () => {
    const next = authFlowReducer(INITIAL_AUTH_FLOW_STATE, { type: "BACKEND_UNHEALTHY" });
    expect(next.status).toBe("backend_offline");
  });

  it("transitions idle → authenticating → authentication_success → redirecting", () => {
    let state: AuthFlowState = { status: "idle" };
    state = authFlowReducer(state, { type: "AUTH_START", method: "password" });
    expect(state.status).toBe("authenticating");

    state = authFlowReducer(state, { type: "AUTH_SUCCESS", redirectTo: "/app" });
    expect(state.status).toBe("authentication_success");

    state = authFlowReducer(state, { type: "REDIRECT_START", redirectTo: "/app" });
    expect(state.status).toBe("redirecting");
  });

  it("blocks AUTH_START when backend_offline", () => {
    const state: AuthFlowState = { status: "backend_offline" };
    const next = authFlowReducer(state, { type: "AUTH_START", method: "password" });
    expect(next.status).toBe("backend_offline");
  });

  it("blocks AUTH_START when checking_backend", () => {
    const next = authFlowReducer(INITIAL_AUTH_FLOW_STATE, { type: "AUTH_START", method: "password" });
    expect(next.status).toBe("checking_backend");
  });

  it("transitions authenticating → authentication_failed on AUTH_FAILURE", () => {
    let state: AuthFlowState = { status: "authenticating", method: "password" };
    state = authFlowReducer(state, {
      type: "AUTH_FAILURE",
      error: { reason: "invalid_credentials", message: "The email or password is incorrect." },
    });
    expect(state.status).toBe("authentication_failed");
    expect(state.error?.reason).toBe("invalid_credentials");
  });

  it("transitions oauth_redirect → oauth_failed on OAUTH_FAILURE", () => {
    let state: AuthFlowState = { status: "oauth_redirect", method: "oauth", provider: "google" };
    state = authFlowReducer(state, {
      type: "OAUTH_FAILURE",
      provider: "google",
      error: { reason: "oauth_cancelled", message: "Google authentication was cancelled." },
    });
    expect(state.status).toBe("oauth_failed");
  });

  it("does not allow BACKEND_UNHEALTHY during authenticating", () => {
    const state: AuthFlowState = { status: "authenticating", method: "password" };
    const next = authFlowReducer(state, { type: "BACKEND_UNHEALTHY" });
    expect(next.status).toBe("authenticating");
  });

  it("does not allow BACKEND_UNHEALTHY during authentication_success", () => {
    const state: AuthFlowState = { status: "authentication_success" };
    const next = authFlowReducer(state, { type: "BACKEND_UNHEALTHY" });
    expect(next.status).toBe("authentication_success");
  });

  it("network_offline → checking_backend on NETWORK_ONLINE", () => {
    const state: AuthFlowState = { status: "network_offline" };
    const next = authFlowReducer(state, { type: "NETWORK_ONLINE" });
    expect(next.status).toBe("checking_backend");
  });

  it("DISMISS_ERROR returns to idle from authentication_failed", () => {
    const state: AuthFlowState = {
      status: "authentication_failed",
      error: { reason: "invalid_credentials", message: "Wrong password" },
    };
    const next = authFlowReducer(state, { type: "DISMISS_ERROR" });
    expect(next.status).toBe("idle");
  });
});

describe("getAuthBanner", () => {
  it("returns only one banner type at a time — never backend_offline + success", () => {
    const offline = getAuthBanner({ status: "backend_offline" });
    const success = getAuthBanner({ status: "authentication_success" });
    const redirecting = getAuthBanner({ status: "redirecting", redirectTo: "/app" });

    expect(offline?.kind).toBe("backend_offline");
    expect(success?.kind).toBe("success");
    expect(redirecting?.kind).toBe("success");
    expect(offline).not.toEqual(success);
  });

  it("returns null for authenticating (spinner on button only)", () => {
    expect(getAuthBanner({ status: "authenticating", method: "password" })).toBeNull();
  });

  it("returns error banner for authentication_failed", () => {
    const banner = getAuthBanner({
      status: "authentication_failed",
      error: { reason: "invalid_credentials", message: "The email or password is incorrect." },
    });
    expect(banner?.kind).toBe("error");
    expect(banner?.message).toContain("incorrect");
  });

  it("returns session_expired banner", () => {
    const banner = getAuthBanner({ status: "session_expired" });
    expect(banner?.kind).toBe("session_expired");
  });
});

describe("selectors", () => {
  it("isAuthInteractive is true only for idle and recoverable error states", () => {
    expect(isAuthInteractive({ status: "idle" })).toBe(true);
    expect(isAuthInteractive({ status: "authentication_failed" })).toBe(true);
    expect(isAuthInteractive({ status: "backend_offline" })).toBe(false);
    expect(isAuthInteractive({ status: "authenticating" })).toBe(false);
  });

  it("isAuthBlocked mirrors non-interactive states", () => {
    expect(isAuthBlocked({ status: "backend_offline" })).toBe(true);
    expect(isAuthBlocked({ status: "idle" })).toBe(false);
  });

  it("isSubmitting covers in-flight auth states", () => {
    expect(isSubmitting({ status: "authenticating" })).toBe(true);
    expect(isSubmitting({ status: "redirecting" })).toBe(true);
    expect(isSubmitting({ status: "idle" })).toBe(false);
  });
});

describe("impossible state combinations", () => {
  const states: AuthFlowState[] = [
    { status: "backend_offline" },
    { status: "authentication_success" },
    { status: "redirecting", redirectTo: "/app" },
    { status: "authentication_failed", error: { reason: "unknown", message: "x" } },
  ];

  it("each state produces at most one banner", () => {
    for (const state of states) {
      const banner = getAuthBanner(state);
      if (banner) {
        expect(typeof banner.kind).toBe("string");
        expect(typeof banner.message).toBe("string");
      }
    }
  });

  it("success states never produce backend_offline banner", () => {
    expect(getAuthBanner({ status: "authentication_success" })?.kind).not.toBe("backend_offline");
    expect(getAuthBanner({ status: "redirecting" })?.kind).not.toBe("backend_offline");
  });
});
