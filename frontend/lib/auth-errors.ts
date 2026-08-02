import { ApiError } from "./api-client";
import type { AuthErrorInfo, AuthFailureReason } from "./auth-state-machine";

const AUTH_ERROR_MESSAGES: Record<AuthFailureReason, string> = {
  invalid_credentials: "The email or password is incorrect.",
  backend_unavailable: "ResearchSwarm is temporarily unavailable. Please try again in a few minutes.",
  network_offline: "You're currently offline. Check your internet connection.",
  oauth_cancelled: "Sign-in was cancelled.",
  oauth_failed: "Sign-in with this provider failed. Please try again.",
  rate_limited: "Too many login attempts. Please wait a few minutes.",
  server_timeout: "The request took too long. Please try again.",
  session_expired: "Your session has expired. Please sign in again.",
  validation: "Please check your input and try again.",
  unknown: "An unexpected error occurred. Please try again.",
};

export function authErrorMessage(reason: AuthFailureReason, override?: string): string {
  return override || AUTH_ERROR_MESSAGES[reason];
}

export function classifyAuthError(error: unknown, context?: { oauth?: boolean; provider?: string }): AuthErrorInfo {
  if (error instanceof DOMException && error.name === "AbortError") {
    const reason: AuthFailureReason = context?.oauth ? "oauth_cancelled" : "unknown";
    const message = context?.provider
      ? `${context.provider.charAt(0).toUpperCase()}${context.provider.slice(1)} authentication was cancelled.`
      : authErrorMessage(reason);
    return { reason, message };
  }

  if (error instanceof ApiError) {
    switch (error.code) {
      case "UNAUTHORIZED":
        return { reason: "invalid_credentials", message: authErrorMessage("invalid_credentials") };
      case "RATE_LIMITED":
        return { reason: "rate_limited", message: authErrorMessage("rate_limited") };
      case "TIMEOUT":
        return { reason: "server_timeout", message: authErrorMessage("server_timeout") };
      case "NETWORK_OFFLINE":
        return { reason: "network_offline", message: authErrorMessage("network_offline") };
      case "OFFLINE":
      case "INTERNAL_ERROR":
        return { reason: "backend_unavailable", message: authErrorMessage("backend_unavailable", error.message) };
      case "VALIDATION_ERROR":
        return { reason: "validation", message: authErrorMessage("validation", error.message) };
      case "ABORTED":
        return {
          reason: context?.oauth ? "oauth_cancelled" : "unknown",
          message: context?.provider
            ? `${context.provider.charAt(0).toUpperCase()}${context.provider.slice(1)} authentication was cancelled.`
            : authErrorMessage("oauth_cancelled"),
        };
      default:
        if (context?.oauth) {
          return { reason: "oauth_failed", message: authErrorMessage("oauth_failed", error.message) };
        }
        return { reason: "unknown", message: authErrorMessage("unknown", error.message) };
    }
  }

  if (error instanceof TypeError) {
    const msg = error.message.toLowerCase();
    if (typeof navigator !== "undefined" && !navigator.onLine) {
      return { reason: "network_offline", message: authErrorMessage("network_offline") };
    }
    if (msg.includes("network") || msg.includes("failed to fetch")) {
      return { reason: "network_offline", message: authErrorMessage("network_offline") };
    }
    return { reason: "backend_unavailable", message: authErrorMessage("backend_unavailable") };
  }

  if (error instanceof Error) {
    if (context?.oauth) {
      return { reason: "oauth_failed", message: authErrorMessage("oauth_failed", error.message) };
    }
    return { reason: "unknown", message: authErrorMessage("unknown", error.message) };
  }

  return { reason: "unknown", message: authErrorMessage("unknown") };
}
