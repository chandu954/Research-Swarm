import type { ProviderSettings } from "./useSettings";
import type { AgentLog, ResearchResult } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("research-swarm-token");
}

export function getTenantIds(): { orgId: string | null; wsId: string | null; projectId: string | null } {
  if (typeof window === "undefined") return { orgId: null, wsId: null, projectId: null };
  return {
    orgId: localStorage.getItem("research-swarm-org-id"),
    wsId: localStorage.getItem("research-swarm-ws-id"),
    projectId: localStorage.getItem("research-swarm-project-id"),
  };
}

function buildHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...extra,
  };
  const token = getAuthToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const { orgId, wsId, projectId } = getTenantIds();
  if (orgId) headers["X-Organization-Id"] = orgId;
  if (wsId) headers["X-Workspace-Id"] = wsId;
  if (projectId) headers["X-Project-Id"] = projectId;
  return headers;
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
  debateMode?: boolean,
) {
  return request<ResearchResult>("/research", {
    method: "POST",
    body: JSON.stringify(researchBody(query, documentIds, providerSettings, streamTaskId, conversationId, debateMode)),
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
  const headers: Record<string, string> = {};
  const token = getAuthToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const { orgId, wsId } = getTenantIds();
  if (orgId) headers["X-Organization-Id"] = orgId;
  if (wsId) headers["X-Workspace-Id"] = wsId;
  const response = await fetch(`${API_URL}/upload`, { method: "POST", body: formData, headers });
  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Upload failed: ${error}`);
  }
  return response.json();
}

export async function listDocuments() {
  return request<any[]>("/documents");
}

export async function listConversations() {
  return request<{ conversations: any[] }>("/conversations");
}

export async function loadConversation(id: string) {
  return request<{ conversation: any; messages: any[] }>(`/conversations/${id}`);
}

export async function healthCheck() {
  return request<{ status: string; version: string; uptime: number }>("/health");
}

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

export async function createConversation(title?: string) {
  return request<any>("/conversations", {
    method: "POST",
    body: JSON.stringify({ title: title || "New Conversation" }),
  });
}

export async function getApiKeys() {
  return request<any[]>("/api-keys");
}

export async function createApiKey(name: string) {
  return request<any>("/api-keys", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function getAuditLogs() {
  return request<any[]>("/audit-logs");
}
