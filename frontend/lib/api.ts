import type { ProviderSettings } from "./useSettings";
import type { AgentLog, ResearchResult, UploadedDocument } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_URL}${endpoint}`;
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
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
  streamTaskId?: string
): Record<string, unknown> {
  const body: Record<string, unknown> = { query, document_ids: documentIds };
  if (streamTaskId) body.stream_task_id = streamTaskId;
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
  streamTaskId?: string
) {
  return request<ResearchResult>("/research", {
    method: "POST",
    body: JSON.stringify(researchBody(query, documentIds, providerSettings, streamTaskId)),
  });
}

/** Subscribe to live agent logs while POST /research runs. */
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
      if (!response.ok || !response.body) {
        throw new Error(`Stream error (${response.status})`);
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
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              if (currentEvent === "log" && data.agent && data.action) {
                callbacks.onLog?.(data as AgentLog);
              }
              if (currentEvent === "done") {
                callbacks.onDone?.();
              }
            } catch {
              /* skip malformed chunks */
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        callbacks.onError?.(err);
      }
    });

  return controller;
}

export function streamResearch(
  query: string,
  documentIds: string[],
  callbacks: {
    onLog?: (log: AgentLog) => void;
    onDone?: () => void;
    onError?: (err: Error) => void;
  }
): AbortController {
  const controller = new AbortController();
  const docParam = documentIds.join(",");
  const url = `${API_URL}/research/stream?query=${encodeURIComponent(query)}&document_ids=${encodeURIComponent(docParam)}`;

  fetch(url, { signal: controller.signal })
    .then(async (response) => {
      if (!response.ok || !response.body) {
        throw new Error(`Stream error (${response.status})`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.agent && data.action) {
                callbacks.onLog?.(data as AgentLog);
              }
            } catch {
              /* skip non-JSON data */
            }
          }
          if (line.startsWith("event: done")) {
            callbacks.onDone?.();
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        callbacks.onError?.(err);
      }
    });

  return controller;
}

export async function uploadPDF(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_URL}/upload`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Upload failed: ${error}`);
  }
  return response.json();
}

export async function listDocuments() {
  return request<{ documents: UploadedDocument[] }>("/documents");
}

export async function listConversations() {
  return request<{ conversations: any[] }>("/conversations");
}

export async function healthCheck() {
  return request<{ status: string; version: string; uptime: number }>("/health");
}
