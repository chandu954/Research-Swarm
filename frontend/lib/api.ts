import type { ProviderSettings } from "./useSettings";
import type { AgentLog, ResearchResult } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getTenantHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const headers: Record<string, string> = {};
  const orgId = localStorage.getItem("research-swarm-org-id");
  const wsId = localStorage.getItem("research-swarm-ws-id");
  if (orgId) headers["X-Organization-Id"] = orgId;
  if (wsId) headers["X-Workspace-Id"] = wsId;
  return headers;
}

function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("research-swarm-token");
  if (token) return { Authorization: `Bearer ${token}` };
  return {};
}

function buildHeaders(extra: Record<string, string> = {}): Record<string, string> {
  return {
    "Content-Type": "application/json",
    ...getAuthHeaders(),
    ...getTenantHeaders(),
    ...extra,
  };
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_URL}${endpoint}`;
  const headers = buildHeaders(options.headers as Record<string, string> || {});
  const response = await fetch(url, { ...options, headers });
  if (!response.ok) {
    const error = await response.text();
    throw new Error(`API error (${response.status}): ${error}`);
  }
  return response.json();
}

function researchBody(
  query: string,
  documentIds: string[],
  providerSettings?: ProviderSettings,
  streamTaskId?: string,
  conversationId?: string,
): Record<string, unknown> {
  const body: Record<string, unknown> = { query, document_ids: documentIds };
  if (streamTaskId) body.stream_task_id = streamTaskId;
  if (conversationId) body.conversation_id = conversationId;
  if (providerSettings) {
    body.llm_provider = providerSettings.provider;
    body.planner_model = providerSettings.plannerModel;
    body.research_model = providerSettings.researchModel;
    body.document_model = providerSettings.documentModel;
    body.answer_model = providerSettings.answerModel;
    if (providerSettings.provider === "openrouter" && providerSettings.openrouterKey) {
      body.openrouter_key = providerSettings.openrouterKey;
    }
  }
  return body;
}

export async function runResearch(
  query: string,
  documentIds: string[] = [],
  providerSettings?: ProviderSettings,
  streamTaskId?: string,
  conversationId?: string,
) {
  const orgId = localStorage.getItem("research-swarm-org-id");
  const params = orgId ? `?organization_id=${orgId}` : "";
  return request<ResearchResult>(`/research${params}`, {
    method: "POST",
    body: JSON.stringify(researchBody(query, documentIds, providerSettings, streamTaskId, conversationId)),
  });
}

export function subscribeResearchLogs(
  taskId: string,
  callbacks: {
    onLog?: (log: AgentLog) => void;
    onDone?: () => void;
    onError?: (err: Error) => void;
  }
): AbortController {
  const controller = new AbortController();
  const url = `${API_URL}/research/stream/${encodeURIComponent(taskId)}`;

  fetch(url, { signal: controller.signal })
    .then(async (response) => {
      if (!response.ok || !response.body) throw new Error(`Stream error (${response.status})`);
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
              if (currentEvent === "done") callbacks.onDone?.();
            } catch { /* skip malformed */ }
          }
        }
      }
    })
    .catch((err) => { if (err.name !== "AbortError") callbacks.onError?.(err); });
  return controller;
}

export async function uploadPDF(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const orgId = localStorage.getItem("research-swarm-org-id");
  const wsId = localStorage.getItem("research-swarm-ws-id");
  const params = new URLSearchParams();
  if (orgId) params.set("organization_id", orgId);
  if (wsId) params.set("workspace_id", wsId);
  const url = `${API_URL}/upload${params.toString() ? "?" + params.toString() : ""}`;
  const headers = getAuthHeaders();
  const response = await fetch(url, { method: "POST", body: formData, headers });
  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Upload failed: ${error}`);
  }
  return response.json();
}

export async function listDocuments() {
  const orgId = localStorage.getItem("research-swarm-org-id");
  const wsId = localStorage.getItem("research-swarm-ws-id");
  const params = new URLSearchParams();
  if (orgId) params.set("organization_id", orgId);
  if (wsId) params.set("workspace_id", wsId);
  const qs = params.toString() ? "?" + params.toString() : "";
  return request<{ documents: any[] }>(`/documents${qs}`);
}

export async function listConversations() {
  const orgId = localStorage.getItem("research-swarm-org-id");
  const wsId = localStorage.getItem("research-swarm-ws-id");
  const params = new URLSearchParams();
  if (orgId) params.set("organization_id", orgId);
  if (wsId) params.set("workspace_id", wsId);
  const qs = params.toString() ? "?" + params.toString() : "";
  return request<{ conversations: any[] }>(`/conversations${qs}`);
}

export async function loadConversation(id: string) {
  return request<{ conversation: any; messages: any[] }>(`/conversations/${id}`);
}

export async function healthCheck() {
  return request<{ status: string; version: string; uptime: number }>("/health");
}

// ── Tenant API ──────────────────────────────────────────────────

export async function listOrganizations() {
  return request<any[]>("/organizations");
}

export async function listWorkspaces(orgId: string) {
  return request<any[]>(`/organizations/${orgId}/workspaces`);
}

export async function listProjects(orgId: string, wsId: string) {
  return request<any[]>(`/organizations/${orgId}/workspaces/${wsId}/projects`);
}

export async function createOrganization(name: string, slug: string) {
  return request<any>("/organizations", {
    method: "POST",
    body: JSON.stringify({ name, slug }),
  });
}

export async function createWorkspace(orgId: string, name: string) {
  return request<any>(`/organizations/${orgId}/workspaces`, {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function createConversation(orgId: string, title?: string, wsId?: string) {
  const params = new URLSearchParams({ organization_id: orgId });
  if (wsId) params.set("workspace_id", wsId);
  return request<any>(`/conversations?${params.toString()}`, {
    method: "POST",
    body: JSON.stringify({ title: title || "New Conversation" }),
  });
}

export async function apiKeys() {
  return request<any[]>("/api-keys");
}

export async function createApiKey(name: string) {
  return request<any>("/api-keys", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function auditLogs() {
  const orgId = localStorage.getItem("research-swarm-org-id");
  return request<any[]>(`/audit-logs?organization_id=${orgId}`);
}
