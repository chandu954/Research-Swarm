"use client";

import { getApiUrl } from "./config";
import type { ProviderSettings } from "./useSettings";
import type { AgentLog, ResearchResult } from "./types";
import {
  ApiError,
  classifyError,
  classifyResponse,
} from "./api-errors";
import {
  api,
  getTenantIds,
  getToken,
  RESEARCH_TIMEOUT_MS,
  STREAM_TIMEOUT_MS,
} from "./api-http";

export {
  ApiError,
  classifyError,
  classifyResponse,
  ApiError as ApiClientError,
} from "./api-errors";
export {
  api,
  TOKEN_KEY,
  REFRESH_KEY,
  ORG_ID_KEY,
  WS_ID_KEY,
  PROJECT_ID_KEY,
} from "./api-http";

/* ───────────────────────────────────────────
   Health check (no auth, no retry, short timeout)
   ─────────────────────────────────────────── */

export async function checkHealth(): Promise<{ ok: boolean; status: string; detail?: string }> {
  try {
    const res = await fetch(`${getApiUrl()}/health`, { method: "GET", signal: AbortSignal.timeout(5000) });
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
  signal?: AbortSignal,
): Promise<ResearchResult> {
  return api.post<ResearchResult>("/research", researchBody(query, documentIds, providerSettings, streamTaskId, conversationId, debateMode), {
    timeout: RESEARCH_TIMEOUT_MS,
    signal,
  });
}

/**
 * Ask the backend to cancel an in-flight research run. The server
 * cancels the tracked background task so provider work terminates and
 * the run is persisted with a terminal "cancelled" status.
 */
export async function cancelResearch(
  taskId: string,
  signal?: AbortSignal,
): Promise<{ status: string; task_id: string; already_done?: boolean }> {
  return api.post<{ status: string; task_id: string; already_done?: boolean }>(
    `/research/${encodeURIComponent(taskId)}/cancel`,
    undefined,
    { signal, timeout: 10_000 },
  );
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
  const url = `${getApiUrl()}/research/stream/${encodeURIComponent(taskId)}`;
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
  id?: string;
  document_id?: string;
  filename: string;
  name?: string;
  original_filename?: string;
  size?: number;
  size_bytes?: number;
  status?: string;
  page_count?: number;
  pages?: number;
  summary?: string;
  auto_tags?: string[];
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

/**
 * Request a short-lived signed download URL for a document.
 *
 * The backend verifies the caller's session and document/workspace
 * ownership, then returns an HMAC-signed URL (opaque, not a JWT) that
 * expires in seconds. The bearer token is never placed in a URL.
 */
export async function getDocumentDownloadUrl(docId: string): Promise<string> {
  const res = await api.post<{ url: string; expires_in: number }>(`/documents/${docId}/download-url`);
  return `${getApiUrl()}${res.url}`;
}

// ── Conversation Actions ──────────────────────────────────

export async function deleteConversation(convId: string) {
  return api.delete<{ status: string }>(`/conversations/${convId}`);
}

export async function updateConversation(convId: string, data: Record<string, unknown>) {
  return api.patch<ConversationSummary>(`/conversations/${convId}`, data);
}

