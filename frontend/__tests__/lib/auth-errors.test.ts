import { describe, it, expect } from "vitest";
import { ApiError } from "@/lib/api-client";
import { classifyAuthError } from "@/lib/auth-errors";

describe("classifyAuthError", () => {
  it("classifies 401 as invalid_credentials", () => {
    const err = new ApiError("Unauthorized", "UNAUTHORIZED", 401, false);
    const result = classifyAuthError(err);
    expect(result.reason).toBe("invalid_credentials");
    expect(result.message).toContain("incorrect");
  });

  it("classifies 429 as rate_limited", () => {
    const err = new ApiError("Too many", "RATE_LIMITED", 429, true);
    const result = classifyAuthError(err);
    expect(result.reason).toBe("rate_limited");
  });

  it("classifies TIMEOUT as server_timeout", () => {
    const err = new ApiError("Timeout", "TIMEOUT", 0, true);
    const result = classifyAuthError(err);
    expect(result.reason).toBe("server_timeout");
  });

  it("classifies NETWORK_OFFLINE separately from OFFLINE", () => {
    const network = classifyAuthError(new ApiError("Offline", "NETWORK_OFFLINE", 0, true));
    const backend = classifyAuthError(new ApiError("Offline", "OFFLINE", 0, true));
    expect(network.reason).toBe("network_offline");
    expect(backend.reason).toBe("backend_unavailable");
    expect(network.message).not.toEqual(backend.message);
  });

  it("classifies OAuth AbortError as oauth_cancelled", () => {
    const err = new DOMException("Popup closed", "AbortError");
    const result = classifyAuthError(err, { oauth: true, provider: "google" });
    expect(result.reason).toBe("oauth_cancelled");
    expect(result.message).toContain("Google");
  });

  it("classifies OAuth ApiError as oauth_failed", () => {
    const err = new ApiError("Provider error", "UNKNOWN", 500, false);
    const result = classifyAuthError(err, { oauth: true, provider: "github" });
    expect(result.reason).toBe("oauth_failed");
  });

  it("does not collapse different failures into the same message", () => {
    const creds = classifyAuthError(new ApiError("Unauthorized", "UNAUTHORIZED", 401, false));
    const rate = classifyAuthError(new ApiError("Too many", "RATE_LIMITED", 429, true));
    const timeout = classifyAuthError(new ApiError("Timeout", "TIMEOUT", 0, true));

    const messages = new Set([creds.message, rate.message, timeout.message]);
    expect(messages.size).toBe(3);
  });
});
