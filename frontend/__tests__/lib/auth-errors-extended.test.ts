import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api-client";
import { classifyAuthError } from "@/lib/auth-errors";

describe("classifyAuthError remaining branches", () => {
  it("classifies VALIDATION_ERROR as validation", () => {
    const err = new ApiError("Bad field", "VALIDATION_ERROR", 422, false);
    const result = classifyAuthError(err);
    expect(result.reason).toBe("validation");
    expect(result.message).toBe("Bad field");
  });

  it("classifies ABORTED with oauth provider as oauth_cancelled", () => {
    const err = new ApiError("Aborted", "ABORTED", 0, false);
    const result = classifyAuthError(err, { oauth: true, provider: "google" });
    expect(result.reason).toBe("oauth_cancelled");
    expect(result.message).toContain("Google");
  });

  it("classifies ABORTED without oauth as unknown with oauth_cancelled message", () => {
    const err = new ApiError("Aborted", "ABORTED", 0, false);
    const result = classifyAuthError(err);
    expect(result.reason).toBe("unknown");
    expect(result.message).toContain("cancelled");
  });

  it("classifies unknown ApiError with oauth context as oauth_failed", () => {
    const err = new ApiError("Provider down", "UNKNOWN", 500, false);
    const result = classifyAuthError(err, { oauth: true, provider: "github" });
    expect(result.reason).toBe("oauth_failed");
    expect(result.message).toContain("Provider down");
  });

  it("classifies unknown ApiError without oauth as unknown", () => {
    const err = new ApiError("Something broke", "UNKNOWN", 500, false);
    const result = classifyAuthError(err);
    expect(result.reason).toBe("unknown");
    expect(result.message).toBe("Something broke");
  });

  it("classifies TypeError when offline as network_offline", () => {
    const err = new TypeError("Failed to fetch");
    Object.defineProperty(navigator, "onLine", { writable: true, value: false });
    const result = classifyAuthError(err);
    expect(result.reason).toBe("network_offline");
  });

  it("classifies TypeError with network message as network_offline", () => {
    const err = new TypeError("network error occurred");
    Object.defineProperty(navigator, "onLine", { writable: true, value: true });
    const result = classifyAuthError(err);
    expect(result.reason).toBe("network_offline");
  });

  it("classifies TypeError with failed to fetch as network_offline", () => {
    const err = new TypeError("failed to fetch resource");
    Object.defineProperty(navigator, "onLine", { writable: true, value: true });
    const result = classifyAuthError(err);
    expect(result.reason).toBe("network_offline");
  });

  it("classifies other TypeError as backend_unavailable", () => {
    const err = new TypeError("some other error");
    Object.defineProperty(navigator, "onLine", { writable: true, value: true });
    const result = classifyAuthError(err);
    expect(result.reason).toBe("backend_unavailable");
  });

  it("classifies generic Error with oauth as oauth_failed", () => {
    const err = new Error("OAuth provider crashed");
    const result = classifyAuthError(err, { oauth: true });
    expect(result.reason).toBe("oauth_failed");
  });

  it("classifies generic Error without oauth as unknown", () => {
    const err = new Error("Something went wrong");
    const result = classifyAuthError(err);
    expect(result.reason).toBe("unknown");
  });

  it("returns unknown for non-Error values", () => {
    const result = classifyAuthError("not an error");
    expect(result.reason).toBe("unknown");
    expect(result.message).toContain("unexpected");
  });

  it("returns unknown for null", () => {
    const result = classifyAuthError(null);
    expect(result.reason).toBe("unknown");
  });

  it("returns unknown for undefined", () => {
    const result = classifyAuthError(undefined);
    expect(result.reason).toBe("unknown");
  });
});
