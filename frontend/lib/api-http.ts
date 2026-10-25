"use client";

import { getApiUrl } from "./config";
import { createLogger } from "./logger";
import {
  ApiError,
  ERROR_CLASSIFICATIONS,
  classifyError,
  classifyResponse,
} from "./api-errors";

export const DEFAULT_TIMEOUT_MS = 30_000;
export const RESEARCH_TIMEOUT_MS = 180_000;
export const STREAM_TIMEOUT_MS = 120_000;
export const MAX_RETRIES = 2;

export const TOKEN_KEY = "research-swarm-token";
export const REFRESH_KEY = "research-swarm-refresh";
export const ORG_ID_KEY = "research-swarm-org-id";
export const WS_ID_KEY = "research-swarm-ws-id";
export const PROJECT_ID_KEY = "research-swarm-project-id";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

export function setToken(t: string | null) {
  if (typeof window === "undefined") return;
  if (t) {
    localStorage.setItem(TOKEN_KEY, t);
    const days = 7;
    const expires = new Date(Date.now() + days * 864e5).toUTCString();
    const secure = location.protocol === "https:" ? "; Secure" : "";
    document.cookie = `${TOKEN_KEY}=${encodeURIComponent(t)}; expires=${expires}; path=/;${secure} SameSite=Lax`;
  } else {
    localStorage.removeItem(TOKEN_KEY);
    const secure = location.protocol === "https:" ? "; Secure" : "";
    document.cookie = `${TOKEN_KEY}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/;${secure} SameSite=Lax`;
  }
}

export function getTenantIds() {
  if (typeof window === "undefined") return { orgId: null, wsId: null, projectId: null };
  return {
    orgId: localStorage.getItem(ORG_ID_KEY),
    wsId: localStorage.getItem(WS_ID_KEY),
    projectId: localStorage.getItem(PROJECT_ID_KEY),
  };
}

/* ───────────────────────────────────────────
   Request Logging
   ─────────────────────────────────────────── */

let requestCounter = 0;
function nextRequestId(): string {
  requestCounter++;
  return `req_${Date.now()}_${requestCounter}`;
}

const requestLog = createLogger("api");

function logRequest(requestId: string, method: string, url: string, status?: number, durationMs?: number, error?: string) {
  requestLog.debug(`${method} ${url}`, { requestId, method, url, status, durationMs, error });
}

/* ───────────────────────────────────────────
   Core fetch with timeout + retry
   ─────────────────────────────────────────── */

export interface RequestOptions {
  method?: string;
  body?: string | FormData;
  headers?: Record<string, string>;
  timeout?: number;
  retryable?: boolean;
  signal?: AbortSignal;
}

async function fetchWithTimeout(url: string, options: RequestOptions, timeout: number): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(url, {
      ...options,
      signal: options.signal || controller.signal,
    });
    return response;
  } finally {
    clearTimeout(timer);
  }
}

async function refreshAccessToken(): Promise<boolean> {
  const rt = getRefreshToken();
  if (!rt) return false;
  try {
    const res = await fetch(`${getApiUrl()}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: rt }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    if (data.access_token) {
      setToken(data.access_token);
      if (data.refresh_token) localStorage.setItem(REFRESH_KEY, data.refresh_token);
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

export async function request<T>(
  endpoint: string,
  options: RequestOptions = {},
): Promise<T> {
  const requestId = nextRequestId();
  const url = `${getApiUrl()}${endpoint}`;
  const timeout = options.timeout ?? DEFAULT_TIMEOUT_MS;
  const maxRetries = options.retryable !== false ? MAX_RETRIES : 0;

  const token = getToken();
  const { orgId, wsId, projectId } = getTenantIds();

  const headers: Record<string, string> = {
    "X-Request-ID": requestId,
    ...options.headers,
  };
  // Never set Content-Type for FormData — browser must set it with the multipart boundary
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (orgId && !headers["X-Organization-Id"]) headers["X-Organization-Id"] = orgId;
  if (wsId && !headers["X-Workspace-Id"]) headers["X-Workspace-Id"] = wsId;
  if (projectId && !headers["X-Project-Id"]) headers["X-Project-Id"] = projectId;

  // Strip content-type header for FormData (browser sets it with boundary)
  const fetchOptions: RequestInit = {
    method: options.method || "GET",
    headers,
  };
  if (options.body) fetchOptions.body = options.body;

  let lastError: ApiError | null = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const start = performance.now();
    try {
      const response = await fetchWithTimeout(url, { ...options, headers: fetchOptions.headers as Record<string, string> }, timeout);

      if (response.ok) {
        const text = await response.text();
        const data = text ? JSON.parse(text) : null;
        logRequest(requestId, options.method || "GET", url, response.status, performance.now() - start);
        return data as T;
      }

      // Parse error body
      let errorBody: Record<string, unknown> = {};
      try {
        const parsed = await response.json();
        if (parsed && typeof parsed === "object") errorBody = parsed as Record<string, unknown>;
      } catch {
        try {
          const text = await response.text();
          if (text) errorBody = { detail: text };
        } catch {}
      }

      const apiError = classifyResponse(response.status, errorBody);

      // Auto-refresh token on 401
      if (response.status === 401 && token && attempt < maxRetries) {
        const refreshed = await refreshAccessToken();
        if (refreshed) {
          // Update auth header with new token
          const newToken = getToken();
          if (newToken) {
            (fetchOptions.headers as Record<string, string>)["Authorization"] = `Bearer ${newToken}`;
            logRequest(requestId, "AUTH", "refreshed token");
            continue; // retry with new token
          }
        }
      }

      lastError = apiError;
      logRequest(requestId, options.method || "GET", url, response.status, performance.now() - start, apiError.message);

      // Don't retry non-retryable errors
      if (!apiError.retryable || attempt >= maxRetries) {
        throw apiError;
      }

      // Exponential backoff
      await new Promise(r => setTimeout(r, Math.min(1000 * Math.pow(2, attempt), 5000)));
    } catch (e) {
      if (e instanceof ApiError) {
        lastError = e;
        if (!e.retryable || attempt >= maxRetries) throw e;
        await new Promise(r => setTimeout(r, Math.min(1000 * Math.pow(2, attempt), 5000)));
        continue;
      }
      const classified = classifyError(e);
      lastError = classified;
      logRequest(requestId, options.method || "GET", url, undefined, performance.now() - start, classified.message);
      if (!classified.retryable || attempt >= maxRetries) throw classified;
      await new Promise(r => setTimeout(r, Math.min(1000 * Math.pow(2, attempt), 5000)));
    }
  }

  throw lastError || new ApiError(ERROR_CLASSIFICATIONS.UNKNOWN.message, "UNKNOWN", 0, true);
}

/* ───────────────────────────────────────────
   Public API
   ─────────────────────────────────────────── */

export const api = {
  get: <T>(endpoint: string, options?: RequestOptions) =>
    request<T>(endpoint, { ...options, method: "GET" }),

  post: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    request<T>(endpoint, {
      ...options,
      method: "POST",
      body: body instanceof FormData ? body : body != null ? JSON.stringify(body) : undefined,
    }),

  put: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    request<T>(endpoint, {
      ...options,
      method: "PUT",
      body: body != null ? JSON.stringify(body) : undefined,
    }),

  delete: <T>(endpoint: string, options?: RequestOptions) =>
    request<T>(endpoint, { ...options, method: "DELETE" }),

  patch: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    request<T>(endpoint, {
      ...options,
      method: "PATCH",
      body: body != null ? JSON.stringify(body) : undefined,
    }),
};
