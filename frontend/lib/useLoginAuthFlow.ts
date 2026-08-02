"use client";

import { useReducer, useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "./auth";
import { API_URL, checkHealth } from "./api-client";
import { classifyAuthError } from "./auth-errors";
import {
  authFlowReducer,
  INITIAL_AUTH_FLOW_STATE,
  isAuthInteractive,
  isSubmitting,
  type AuthFlowState,
  type AuthFlowAction,
  getAuthBanner,
  isAuthBlocked,
} from "./auth-state-machine";

const HEALTH_CHECK_INTERVAL_MS = 30_000;
const REDIRECT_DELAY_MS = 300;

export interface UseLoginAuthFlowOptions {
  onSessionExpired?: boolean;
}

export function useLoginAuthFlow(options: UseLoginAuthFlowOptions = {}) {
  const router = useRouter();
  const { login, register, oauthLogin } = useAuth();
  const [state, dispatch] = useReducer(authFlowReducer, INITIAL_AUTH_FLOW_STATE);
  const submitLockRef = useRef(false);
  const redirectStartedRef = useRef(false);
  const uiSuccessRef = useRef(false);
  const healthIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const statusRef = useRef(state.status);
  statusRef.current = state.status;

  const runHealthCheck = useCallback(async () => {
    if (typeof navigator !== "undefined" && !navigator.onLine) {
      dispatch({ type: "NETWORK_OFFLINE" });
      return;
    }

    dispatch({ type: "CHECK_BACKEND_START" });

    const result = await checkHealth();
    if (result.ok) {
      dispatch({ type: "BACKEND_HEALTHY" });
    } else {
      dispatch({ type: "BACKEND_UNHEALTHY" });
    }
  }, []);

  // Initial health check + 30s retry while offline
  useEffect(() => {
    void runHealthCheck();

    healthIntervalRef.current = setInterval(() => {
      const s = statusRef.current;
      if (s === "backend_offline" || s === "network_offline" || s === "checking_backend") {
        void runHealthCheck();
      }
    }, HEALTH_CHECK_INTERVAL_MS);

    return () => {
      if (healthIntervalRef.current) clearInterval(healthIntervalRef.current);
    };
  }, [runHealthCheck]);

  // Browser online/offline events
  useEffect(() => {
    const handleOnline = () => {
      dispatch({ type: "NETWORK_ONLINE" });
      void runHealthCheck();
    };
    const handleOffline = () => dispatch({ type: "NETWORK_OFFLINE" });

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, [runHealthCheck]);

  // Session expired query param / option
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (options.onSessionExpired) {
      dispatch({ type: "SESSION_EXPIRED" });
    }
    const params = new URLSearchParams(window.location.search);
    if (params.get("session") === "expired") {
      dispatch({ type: "SESSION_EXPIRED" });
    }
  }, [options.onSessionExpired]);

  // Redirect once after success
  useEffect(() => {
    if (state.status !== "authentication_success" || redirectStartedRef.current) return;

    const destination = state.redirectTo || "/app";
    redirectStartedRef.current = true;
    dispatch({ type: "REDIRECT_START", redirectTo: destination });
    window.setTimeout(() => router.push(destination), REDIRECT_DELAY_MS);
  }, [state.status, state.redirectTo, router]);

  const dispatchAction = useCallback((action: AuthFlowAction) => {
    dispatch(action);
  }, []);

  const performLogin = useCallback(
    async (email: string, password: string) => {
      if (submitLockRef.current) return;
      submitLockRef.current = true;
      dispatch({ type: "AUTH_START", method: "password" });

      try {
        await login(email, password);
        uiSuccessRef.current = true;
        dispatch({ type: "AUTH_SUCCESS", redirectTo: "/app" });
      } catch (err) {
        const error = classifyAuthError(err);
        dispatch({ type: "AUTH_FAILURE", error });
        submitLockRef.current = false;
        throw err;
      }
    },
    [login],
  );

  const performRegister = useCallback(
    async (email: string, password: string, name: string) => {
      if (submitLockRef.current) return;
      submitLockRef.current = true;
      dispatch({ type: "AUTH_START", method: "password" });

      try {
        await register(email, password, name);
        uiSuccessRef.current = true;
        dispatch({ type: "AUTH_SUCCESS", redirectTo: "/app" });
      } catch (err) {
        const error = classifyAuthError(err);
        dispatch({ type: "AUTH_FAILURE", error });
        submitLockRef.current = false;
        throw err;
      }
    },
    [register],
  );

  const performOAuth = useCallback(
    async (provider: "google" | "github" | "microsoft") => {
      if (submitLockRef.current) return;
      submitLockRef.current = true;
      dispatch({ type: "OAUTH_REDIRECT", provider });

      try {
        await oauthLogin(provider);
        uiSuccessRef.current = true;
        dispatch({ type: "AUTH_SUCCESS", redirectTo: "/app" });
      } catch (err) {
        const error = classifyAuthError(err, { oauth: true, provider });
        dispatch({ type: "OAUTH_FAILURE", provider, error });
        submitLockRef.current = false;
      }
    },
    [oauthLogin],
  );

  const dismissError = useCallback(() => {
    submitLockRef.current = false;
    dispatch({ type: "DISMISS_ERROR" });
  }, []);

  const resetFlow = useCallback(() => {
    submitLockRef.current = false;
    redirectStartedRef.current = false;
    uiSuccessRef.current = false;
    dispatch({ type: "RESET" });
    void runHealthCheck();
  }, [runHealthCheck]);

  const banner = (() => {
    const freezeSuccess =
      uiSuccessRef.current ||
      state.status === "authentication_success" ||
      state.status === "redirecting" ||
      redirectStartedRef.current;

    if (process.env.NODE_ENV === "development") {
      // Helps confirm why backend_offline banner appears during success flow.
      // eslint-disable-next-line no-console
      console.debug("[auth-flow][banner]", {
        freezeSuccess,
        uiSuccess: uiSuccessRef.current,
        fsm: state.status,
        redirectStarted: redirectStartedRef.current,
      });
    }

    if (freezeSuccess) {
      return { kind: "success", message: "Success! Redirecting..." } as const;
    }

    return getAuthBanner(state);
  })();

  return {
    state,
    banner,
    isInteractive: isAuthInteractive(state),
    isBlocked: isAuthBlocked(state),
    isSubmitting: isSubmitting(state),
    isOAuthLoading: (provider: string) =>
      (state.status === "oauth_redirect" || state.status === "authenticating") &&
      state.method === "oauth" &&
      state.provider === provider,
    performLogin,
    performRegister,
    performOAuth,
    dismissError,
    resetFlow,
    dispatch: dispatchAction,
    apiUrl: API_URL,
  };
}

export type { AuthFlowState, AuthFlowAction };
