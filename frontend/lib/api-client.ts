"use client";

import type { ProviderSettings } from "./useSettings";
import type { AgentLog, ResearchResult } from "./types";

/* ───────────────────────────────────────────
   Error Classification
   ─────────────────────────────────────────── */

export class ApiError extends Error {
  code: string;
  status: number;
  retryable: boolean;
  constructor(message: string, code: string, status: number, retryable = false) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.retryable = retryable;
  }
}

const ERROR_CLASSIFICATIONS: Record<string, { message: string; retryable: boolean }> = {
  OFFLINE:            { message: "ResearchSwarm is temporarily unavailable. Please try again in a few minutes.", retryable: true },
  CORS_ERROR:         { message: "Unable to connect to the backend service. Please contact support.", retryable: false },
  DNS_ERROR:          { message: "Unable to resolve the backend server address. Check your internet connection.", retryable: true },
  NETWORK_OFFLINE:    { message: "You're currently offline. Please check your internet connection.", retryable: true },
  TIMEOUT:            { message: "The request took too long. Please try again.", retryable: true },
  UNAUTHORIZED:       { message: "The email or password is incorrect.", retryable: false },
  FORBIDDEN:          { message: "You do not have permission to perform this action.", retryable: false },
  NOT_FOUND:          { message: "The requested resource was not found.", retryable: false },
  RATE_LIMITED:       { message: "Too many login attempts. Please wait a few minutes.", retryable: true },
  VALIDATION_ERROR:   { message: "Please check your input and try again.", retryable: false },
  ORGANIZATION_REQUIRED: { message: "Finish setting up your workspace.", retryable: false },
  INTERNAL_ERROR:     { message: "Something went wrong while processing your request. Our team has been notified.", retryable: true },
  ABORTED:            { message: "Request was cancelled.", retryable: false },
  UNKNOWN:            { message: "An unexpected error occurred. Please try again.", retryable: true },
};

function classifyError(e: unknown): ApiError {
  if (e instanceof ApiError) return e;
  if (e instanceof DOMException && e.name === "AbortError") {
    return new ApiError(ERROR_CLASSIFICATIONS.ABORTED.message, "ABORTED", 0, false);
  }
  if (e instanceof TypeError) {
    const msg = e.message.toLowerCase();
    // CORS errors — distinct from network offline
    if (msg.includes("cors") || msg.includes("cross-origin")) {
      return new ApiError(ERROR_CLASSIFICATIONS.CORS_ERROR.message, "CORS_ERROR", 0, false);
    }
    // DNS / name resolution failure
    if (msg.includes("enotfound") || msg.includes("dns") || msg.includes("name not resolved") || msg.includes("getaddrinfo")) {
      return new ApiError(ERROR_CLASSIFICATIONS.DNS_ERROR.message, "DNS_ERROR", 0, true);
    }
    // Network offline (no internet connection)
    if (msg.includes("network") || msg.includes("networkerror") || msg.includes("err_network")) {
      return new ApiError(ERROR_CLASSIFICATIONS.NETWORK_OFFLINE.message, "NETWORK_OFFLINE", 0, true);
    }
    // fetch failure (server unreachable)
    if (msg.includes("fetch") || msg.includes("failed to fetch")) {
      return new ApiError(ERROR_CLASSIFICATIONS.OFFLINE.message, "OFFLINE", 0, true);
    }
    return new ApiError(ERROR_CLASSIFICATIONS.OFFLINE.message, "OFFLINE", 0, true);
  }
  if (e instanceof Error) {
    return new ApiError(e.message, "UNKNOWN", 0, true);
  }
  return new ApiError(ERROR_CLASSIFICATIONS.UNKNOWN.message, "UNKNOWN", 0, true);
}

function classifyResponse(status: number, body: Record<string, unknown>): ApiError {
  const code = typeof body.code === "string" ? body.code : typeof (body.detail as Record<string, unknown>)?.code === "string" ? (body.detail as Record<string, unknown>).code as string : "";
  const detailRaw = (body.detail as Record<string, unknown>)?.message || body.detail || body.message || body.error || "";
  const detail = typeof detailRaw === "string" ? detailRaw : String(detailRaw);

  if (status === 401) return new ApiError(ERROR_CLASSIFICATIONS.UNAUTHORIZED.message, "UNAUTHORIZED", status, false);
  if (status === 403) {
    if (code === "organization_required") {
      return new ApiError(ERROR_CLASSIFICATIONS.ORGANIZATION_REQUIRED.message, "ORGANIZATION_REQUIRED", status, false);
    }
    return new ApiError(ERROR_CLASSIFICATIONS.FORBIDDEN.message, "FORBIDDEN", status, false);
  }
  if (status === 404) return new ApiError(detail || ERROR_CLASSIFICATIONS.NOT_FOUND.message, "NOT_FOUND", status, false);
  if (status === 429) return new ApiError(ERROR_CLASSIFICATIONS.RATE_LIMITED.message, "RATE_LIMITED", status, true);
  if (status === 422) return new ApiError(detail || ERROR_CLASSIFICATIONS.VALIDATION_ERROR.message, "VALIDATION_ERROR", status, false);
  if (status >= 500) return new ApiError(detail || ERROR_CLASSIFICATIONS.INTERNAL_ERROR.message, "INTERNAL_ERROR", status, true);
  return new ApiError(detail || `Request failed (${status})`, "UNKNOWN", status, false);
}

/* ───────────────────────────────────────────
   Configuration
   ─────────────────────────────────────────── */

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const DEFAULT_TIMEOUT_MS = 30_000;
const RESEARCH_TIMEOUT_MS = 180_000;
const STREAM_TIMEOUT_MS = 120_000;
const MAX_RETRIES = 2;

export const TOKEN_KEY = "research-swarm-token";
export const REFRESH_KEY = "research-swarm-refresh";
export const ORG_ID_KEY = "research-swarm-org-id";
export const WS_ID_KEY = "research-swarm-ws-id";
export const PROJECT_ID_KEY = "research-swarm-project-id";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

function setToken(t: string | null) {
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

function getTenantIds() {
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

function logRequest(requestId: string, method: string, url: string, status?: number, durationMs?: number, error?: string) {
  if (process.env.NODE_ENV === "development") {
    const prefix = `[API ${requestId}]`;
    const parts = [prefix, method, url];
    if (status) parts.push(`→ ${status}`);
    if (durationMs != null) parts.push(`${durationMs}ms`);
    if (error) parts.push(`ERROR: ${error}`);
    console.debug(...parts);
  }
}

/* ───────────────────────────────────────────
   Core fetch with timeout + retry
   ─────────────────────────────────────────── */

interface RequestOptions {
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
    const res = await fetch(`${API_URL}/auth/refresh`, {
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

async function request<T>(
  endpoint: string,
  options: RequestOptions = {},
): Promise<T> {
  const requestId = nextRequestId();
  const url = `${API_URL}${endpoint}`;
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

/* ───────────────────────────────────────────
   Health check (no auth, no retry, short timeout)
   ─────────────────────────────────────────── */

export async function checkHealth(): Promise<{ ok: boolean; status: string; detail?: string }> {
  try {
    const res = await fetch(`${API_URL}/health`, { method: "GET", signal: AbortSignal.timeout(5000) });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      return { ok: false, status: `HTTP ${res.status}`, detail: body.detail };
    }
    const data = await res.json();
    return { ok: true, status: data.status || "healthy" };
  } catch (e: unknown) {
    return { ok: false, status: "offline", detail: e instanceof Error ? e.message : String(e) };
  }
}

/* ───────────────────────────────────────────
   Research (POST - uses request)
   ─────────────────────────────────────────── */

function researchBody(
  query: string,
  documentIds: string[],
  providerSettings?: ProviderSettings,
  streamTaskId?: string,
  conversationId?: string,
  debateMode?: boolean,
): Record<string, unknown> {
  const body: Record<string, unknown> = { query, document_ids: documentIds };
  if (streamTaskId) body.stream_task_id = streamTaskId;
  if (conversationId) body.conversation_id = conversationId;
  if (debateMode) body.debate_mode = true;
    if (providerSettings) {
      body.llm_provider = providerSettings.provider;
      body.planner_model = providerSettings.plannerModel;
      body.research_model = providerSettings.researchModel;
      body.document_model = providerSettings.documentModel;
      body.answer_model = providerSettings.answerModel;
    }
  return body;
}

export async function runResearch(
  query: string,
  documentIds: string[] = [],
  providerSettings?: ProviderSettings,
  streamTaskId?: string,
  conversationId?: string,
  debateMode?: boolean,
): Promise<ResearchResult> {
  return api.post<ResearchResult>("/research", researchBody(query, documentIds, providerSettings, streamTaskId, conversationId, debateMode), {
    timeout: RESEARCH_TIMEOUT_MS,
  });
}

/* ───────────────────────────────────────────
   Research stream (SSE)
   ─────────────────────────────────────────── */

export function subscribeResearchLogs(
  taskId: string,
  callbacks: {
    onLog?: (log: AgentLog) => void;
    onDone?: () => void;
    onError?: (err: ApiError) => void;
  },
): AbortController {
  const controller = new AbortController();
  const url = `${API_URL}/research/stream/${encodeURIComponent(taskId)}`;
  const token = getToken();
  const { orgId, wsId } = getTenantIds();

  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (orgId) headers["X-Organization-Id"] = orgId;
  if (wsId) headers["X-Workspace-Id"] = wsId;

  const timer = setTimeout(() => controller.abort(), STREAM_TIMEOUT_MS);

  (async () => {
    try {
      const response = await fetch(url, { headers, signal: controller.signal });
      if (!response.ok || !response.body) {
        const errorBody = await response.json().catch(() => ({}));
        throw classifyResponse(response.status, errorBody);
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (line.startsWith("event: ")) currentEvent = line.slice(7).trim();
          else if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              if (currentEvent === "log" && data.agent && data.action) callbacks.onLog?.(data as AgentLog);
              if (currentEvent === "done") { clearTimeout(timer); callbacks.onDone?.(); }
            } catch { /* skip malformed */ }
          }
        }
      }
      clearTimeout(timer);
      callbacks.onDone?.();
    } catch (err: unknown) {
      clearTimeout(timer);
      if (err instanceof DOMException && err.name === "AbortError") return;
      callbacks.onError?.(err instanceof ApiError ? err : classifyError(err));
    }
  })();

  return controller;
}

/* ───────────────────────────────────────────
   Upload
   ─────────────────────────────────────────── */

export interface UploadResult {
  document_id: string;
  filename: string;
  original_filename?: string;
  size: number;
  status: string;
  page_count?: number;
}

export async function uploadPDF(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return api.post<UploadResult>("/upload", formData, { timeout: 60_000 });
}

/* ───────────────────────────────────────────
   Convenience wrappers
   ─────────────────────────────────────────── */

export interface DocumentInfo {
  document_id: string;
  filename: string;
  original_filename?: string;
  size: number;
  status: string;
  page_count?: number;
  created_at?: string;
}

export interface ConversationSummary {
  id: string;
  title?: string;
  created_at?: string;
  updated_at?: string;
  message_count?: number;
}

export interface OrganizationInfo {
  id: string;
  name: string;
  slug: string;
  owner_id: string;
  member_count: number;
}

export interface WorkspaceInfo {
  id: string;
  name: string;
  organization_id: string;
}

export interface ProjectInfo {
  id: string;
  name: string;
  workspace_id: string;
}

export interface ApiKeyInfo {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at?: string;
}

export interface AuditLogEntry {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string;
  created_at: string;
  details?: Record<string, unknown>;
}

export async function listDocuments() {
  return api.get<DocumentInfo[]>("/documents");
}

export async function listConversations() {
  return api.get<ConversationSummary[]>("/conversations");
}

export interface ConversationMessageResponse {
  id: string;
  message_id?: string;
  role: string;
  content: string;
  timestamp?: number;
  sources?: Array<{ source_type: string; title: string; url?: string }>;
}

export async function loadConversation(id: string) {
  return api.get<{ id: string; title?: string; messages: ConversationMessageResponse[] }>(`/conversations/${id}`);
}

export async function healthCheck() {
  return api.get<{ status: string; version: string; uptime: number }>("/health");
}

export async function listOrganizations() {
  return api.get<OrganizationInfo[]>("/organizations");
}

export async function listWorkspaces(orgId: string) {
  return api.get<WorkspaceInfo[]>(`/organizations/${orgId}/workspaces`);
}

export async function listProjects(orgId: string, wsId: string) {
  return api.get<ProjectInfo[]>(`/organizations/${orgId}/workspaces/${wsId}/projects`);
}

export async function createOrganization(name: string, slug: string) {
  return api.post<OrganizationInfo>("/organizations", { name, slug });
}

export async function createWorkspace(orgId: string, name: string) {
  return api.post<WorkspaceInfo>(`/organizations/${orgId}/workspaces`, { name });
}

export async function createConversation(title?: string) {
  return api.post<ConversationSummary>("/conversations", { title: title || "New Conversation" });
}

export async function getApiKeys() {
  return api.get<ApiKeyInfo[]>("/api-keys");
}

export async function createApiKey(name: string) {
  return api.post<ApiKeyInfo>("/api-keys", { name });
}

export async function getAuditLogs() {
  return api.get<AuditLogEntry[]>("/audit-logs");
}

// ── Document Actions ───────────────────────────────────────

export async function deleteDocument(docId: string) {
  return api.delete<{ status: string }>(`/documents/${docId}`);
}

export function getDocumentDownloadUrl(docId: string) {
  return `${API_URL}/documents/${docId}/download`;
}

// ── Conversation Actions ──────────────────────────────────

export async function deleteConversation(convId: string) {
  return api.delete<{ status: string }>(`/conversations/${convId}`);
}

export async function updateConversation(convId: string, data: Record<string, unknown>) {
  return api.patch<ConversationSummary>(`/conversations/${convId}`, data);
}

export { classifyError, classifyResponse, ApiError as ApiClientError };
