/**
 * Deterministic authentication flow state machine.
 * Exactly one status is active at any time — mutually exclusive UI states.
 */

export type AuthFlowStatus =
  | "idle"
  | "checking_backend"
  | "backend_offline"
  | "network_offline"
  | "authenticating"
  | "authentication_success"
  | "redirecting"
  | "authentication_failed"
  | "oauth_redirect"
  | "oauth_failed"
  | "session_expired";

export type AuthFailureReason =
  | "invalid_credentials"
  | "backend_unavailable"
  | "network_offline"
  | "oauth_cancelled"
  | "oauth_failed"
  | "rate_limited"
  | "server_timeout"
  | "session_expired"
  | "validation"
  | "unknown";

export interface AuthErrorInfo {
  reason: AuthFailureReason;
  message: string;
}

export interface AuthFlowState {
  status: AuthFlowStatus;
  /** Present while authenticating or during oauth_redirect */
  method?: "password" | "oauth";
  provider?: string;
  error?: AuthErrorInfo;
  redirectTo?: string;
}

export type AuthFlowAction =
  | { type: "CHECK_BACKEND_START" }
  | { type: "BACKEND_HEALTHY" }
  | { type: "BACKEND_UNHEALTHY" }
  | { type: "NETWORK_OFFLINE" }
  | { type: "NETWORK_ONLINE" }
  | { type: "AUTH_START"; method: "password" | "oauth"; provider?: string }
  | { type: "AUTH_SUCCESS"; redirectTo?: string }
  | { type: "AUTH_FAILURE"; error: AuthErrorInfo }
  | { type: "OAUTH_REDIRECT"; provider: string }
  | { type: "OAUTH_FAILURE"; provider: string; error: AuthErrorInfo }
  | { type: "REDIRECT_START"; redirectTo: string }
  | { type: "SESSION_EXPIRED" }
  | { type: "DISMISS_ERROR" }
  | { type: "RESET" };

export const INITIAL_AUTH_FLOW_STATE: AuthFlowState = {
  status: "checking_backend",
};

const TERMINAL_OR_IN_FLIGHT: AuthFlowStatus[] = [
  "authenticating",
  "authentication_success",
  "redirecting",
  "oauth_redirect",
];

/** States where user interaction (login/OAuth) is allowed */
export function isAuthInteractive(state: AuthFlowState): boolean {
  return (
    state.status === "idle" ||
    state.status === "authentication_failed" ||
    state.status === "oauth_failed" ||
    state.status === "session_expired"
  );
}

export function isAuthBlocked(state: AuthFlowState): boolean {
  return !isAuthInteractive(state);
}

export function isSubmitting(state: AuthFlowState): boolean {
  return (
    state.status === "authenticating" ||
    state.status === "oauth_redirect" ||
    state.status === "redirecting" ||
    state.status === "authentication_success"
  );
}

export function isOAuthLoading(state: AuthFlowState, provider: string): boolean {
  return (
    (state.status === "oauth_redirect" || state.status === "authenticating") &&
    state.method === "oauth" &&
    state.provider === provider
  );
}

export type BannerKind = "checking" | "backend_offline" | "network_offline" | "error" | "success" | "session_expired";

export interface AuthBanner {
  kind: BannerKind;
  message: string;
}

/**
 * Returns at most one banner for the current auth state.
 * Never combines backend-offline with success.
 */
export function getAuthBanner(state: AuthFlowState): AuthBanner | null {
  switch (state.status) {
    case "checking_backend":
      return {
        kind: "checking",
        message: "Connecting to ResearchSwarm...",
      };
    case "backend_offline":
      return {
        kind: "backend_offline",
        message: "ResearchSwarm backend is currently offline. Please try again in a few minutes.",
      };
    case "network_offline":
      return {
        kind: "network_offline",
        message: "You're currently offline. Check your internet connection.",
      };
    case "authentication_failed":
      return state.error
        ? { kind: "error", message: state.error.message }
        : null;
    case "oauth_failed":
      return state.error
        ? { kind: "error", message: state.error.message }
        : null;
    case "session_expired":
      return {
        kind: "session_expired",
        message: "Your session has expired. Please sign in again.",
      };
    case "authentication_success":
    case "redirecting":
      return {
        kind: "success",
        message: "Success! Redirecting...",
      };
    default:
      return null;
  }
}

function canTransitionFrom(current: AuthFlowStatus, action: AuthFlowAction["type"]): boolean {
  if (TERMINAL_OR_IN_FLIGHT.includes(current)) {
    if (action === "AUTH_SUCCESS") return current === "authenticating" || current === "oauth_redirect";
    if (action === "AUTH_FAILURE") return current === "authenticating";
    if (action === "OAUTH_FAILURE") return current === "oauth_redirect" || current === "authenticating";
    if (action === "REDIRECT_START") return current === "authentication_success";
    if (action === "BACKEND_HEALTHY" || action === "BACKEND_UNHEALTHY" || action === "NETWORK_OFFLINE") {
      return false;
    }
  }
  return true;
}

export function authFlowReducer(state: AuthFlowState, action: AuthFlowAction): AuthFlowState {
  switch (action.type) {
    case "CHECK_BACKEND_START":
      if (state.status === "idle" || state.status === "backend_offline" || state.status === "network_offline") {
        return { status: "checking_backend" };
      }
      if (TERMINAL_OR_IN_FLIGHT.includes(state.status)) {
        return state;
      }
      return { status: "checking_backend" };

    case "BACKEND_HEALTHY":
      if (TERMINAL_OR_IN_FLIGHT.includes(state.status)) return state;
      return { status: "idle" };

    case "BACKEND_UNHEALTHY":
      if (TERMINAL_OR_IN_FLIGHT.includes(state.status)) return state;
      return { status: "backend_offline" };

    case "NETWORK_OFFLINE":
      if (TERMINAL_OR_IN_FLIGHT.includes(state.status)) return state;
      return { status: "network_offline" };

    case "NETWORK_ONLINE":
      if (state.status === "network_offline") {
        return { status: "checking_backend" };
      }
      return state;

    case "AUTH_START":
      if (!isAuthInteractive(state) && state.status !== "checking_backend") {
        if (state.status === "checking_backend") return state;
        if (!canTransitionFrom(state.status, action.type)) return state;
      }
      if (state.status === "backend_offline" || state.status === "network_offline" || state.status === "checking_backend") {
        return state;
      }
      return {
        status: "authenticating",
        method: action.method,
        provider: action.provider,
      };

    case "OAUTH_REDIRECT":
      if (state.status === "backend_offline" || state.status === "network_offline" || state.status === "checking_backend") {
        return state;
      }
      if (!isAuthInteractive(state)) return state;
      return {
        status: "oauth_redirect",
        method: "oauth",
        provider: action.provider,
      };

    case "AUTH_SUCCESS":
      if (state.status !== "authenticating" && state.status !== "oauth_redirect") return state;
      return {
        status: "authentication_success",
        redirectTo: action.redirectTo,
      };

    case "REDIRECT_START":
      if (state.status !== "authentication_success") return state;
      return {
        status: "redirecting",
        redirectTo: action.redirectTo,
      };

    case "AUTH_FAILURE":
      if (state.status !== "authenticating") return state;
      return {
        status: "authentication_failed",
        error: action.error,
      };

    case "OAUTH_FAILURE":
      if (state.status !== "oauth_redirect" && state.status !== "authenticating") return state;
      return {
        status: "oauth_failed",
        provider: action.provider,
        error: action.error,
      };

    case "SESSION_EXPIRED":
      if (TERMINAL_OR_IN_FLIGHT.includes(state.status)) return state;
      return { status: "session_expired" };

    case "DISMISS_ERROR":
      if (
        state.status === "authentication_failed" ||
        state.status === "oauth_failed" ||
        state.status === "session_expired"
      ) {
        return { status: "idle" };
      }
      return state;

    case "RESET":
      return { status: "checking_backend" };

    default:
      return state;
  }
}
