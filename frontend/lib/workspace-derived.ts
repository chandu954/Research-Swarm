import { ApiClientError, listDocuments } from "@/lib/api";
import type { RealtimeDocument } from "@/lib/supabase/realtime";
import type {
  AgentLog,
  Message,
  SourceCitation,
  UploadedDocument,
} from "@/lib/types";

export interface ConversationMessageResponse {
  id?: string;
  message_id?: string;
  role: string;
  content?: string;
  created_at?: number;
  timestamp?: number;
  sources?: SourceCitation[];
}

export type ResearchPhase = "idle" | "running" | "completed" | "failed";

export function errorCopy(error: unknown): { message: string; runError: string } {
  if (error instanceof ApiClientError) {
    const hint =
      error.code === "OFFLINE"
        ? "The backend may be offline. Check your connection."
        : error.code === "TIMEOUT"
          ? "The research took too long. Try a simpler query."
          : error.code === "UNAUTHORIZED"
            ? "Your session expired. Please sign in again."
            : "";
    return {
      message: `**${error.message}**\n\n> ${hint}`,
      runError:
        error.code === "OFFLINE"
          ? "The backend may be offline. Check your connection and try again."
          : error.code === "TIMEOUT"
            ? "The research took too long. Try again or use a simpler query."
            : error.code === "UNAUTHORIZED"
              ? "Your session expired. Please sign in again."
              : error.message,
    };
  }
  const message =
    error instanceof Error ? error.message : "An unexpected error occurred. Please try again.";
  return { message: `**Error**: ${message}`, runError: message };
}

export function mapConversationMessages(messages: ConversationMessageResponse[]): Message[] {
  return messages.map((m) => ({
    id: m.id || m.message_id || crypto.randomUUID(),
    role: m.role as Message["role"],
    content: m.content || "",
    timestamp: m.created_at || m.timestamp || Date.now(),
    sources: m.sources || [],
  }));
}

export function mapUploadedDocuments(
  existingDocuments: Awaited<ReturnType<typeof listDocuments>>,
): UploadedDocument[] {
  return (Array.isArray(existingDocuments) ? existingDocuments : []).map(
    (doc): UploadedDocument => ({
      document_id: doc.id ?? doc.document_id ?? "",
      filename: doc.filename ?? doc.name ?? "",
      original_filename: doc.original_filename ?? doc.filename ?? "",
      size: doc.size_bytes ?? doc.size ?? 0,
      status: doc.status ?? "ready",
      page_count: doc.page_count ?? doc.pages ?? undefined,
      summary: doc.summary,
      auto_tags: doc.auto_tags ?? [],
    }),
  );
}

export function mergeAgentLogs(logs: AgentLog[], realtimeLogs: AgentLog[]): AgentLog[] {
  const next = [...logs];
  for (const rtLog of realtimeLogs) {
    const idx = next.findIndex(
      (l) => l.agent === rtLog.agent && l.action === rtLog.action,
    );
    if (idx >= 0) {
      const existing = next[idx];
      if (existing.status === "completed") continue;
      next[idx] = rtLog;
    } else {
      next.push(rtLog);
    }
  }
  return next;
}

export function mergeDocuments(
  documents: UploadedDocument[],
  realtimeDocuments: RealtimeDocument[],
): UploadedDocument[] {
  const next = [...documents];
  for (const rtDoc of realtimeDocuments) {
    if (next.some((d) => d.document_id === rtDoc.id)) continue;
    next.push({
      document_id: rtDoc.id,
      filename: rtDoc.name,
      original_filename: rtDoc.name,
      size: rtDoc.size_bytes ?? 0,
      status: rtDoc.status,
      page_count: rtDoc.pages ?? undefined,
    });
  }
  return next;
}

export function researchPhase(
  isRunning: boolean,
  runError: string | null,
  messageCount: number,
): ResearchPhase {
  if (isRunning) return "running";
  if (runError) return "failed";
  return messageCount === 0 ? "idle" : "completed";
}
