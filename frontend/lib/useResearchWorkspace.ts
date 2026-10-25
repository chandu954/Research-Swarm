"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  ApiClientError,
  cancelResearch,
  listDocuments,
  loadConversation,
  runResearch,
  subscribeResearchLogs,
  uploadPDF,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { logger } from "@/lib/logger";
import { useProviderSettings } from "@/lib/useSettings";
import { collaborationClient } from "@/lib/websocket";
import { useTenant } from "@/lib/tenant";
import { useRealtimeWorkspace } from "@/lib/supabase/realtime";
import { useLiveWorkspace } from "@/lib/supabase/query";
import {
  errorCopy,
  mapConversationMessages,
  mapUploadedDocuments,
  mergeAgentLogs,
  mergeDocuments,
  researchPhase,
} from "@/lib/workspace-derived";
import type {
  AgentMetric,
  AgentLog,
  ExecutionStep,
  Message,
  SourceCitation,
  UploadedDocument,
} from "@/lib/types";

const log = logger.child("workspace");


export function useResearchWorkspace() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [logs, setLogs] = useState<AgentLog[]>([]);
  const [plan, setPlan] = useState<ExecutionStep[]>([]);
  const [sources, setSources] = useState<SourceCitation[]>([]);
  const [agentMetrics, setAgentMetrics] = useState<Record<string, AgentMetric>>({});
  const [executionTime, setExecutionTime] = useState<number>();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [workflowOpen, setWorkflowOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [conversationsRefreshKey, setConversationsRefreshKey] = useState(0);
  const [inspectedSource, setInspectedSource] = useState<SourceCitation | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [supabaseSessionId, setSupabaseSessionId] = useState<string | null>(null);
  const [debateMode, setDebateMode] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const { settings: providerSettings, update: setProviderSettings } = useProviderSettings();
  const { user, token } = useAuth();
  const { currentWorkspace } = useTenant();
  const workspaceId = currentWorkspace?.id;
  const currentUserId = user?.id;
  const realtime = useRealtimeWorkspace(supabaseSessionId);
  const live = useLiveWorkspace();
  const refreshLiveWorkspace = live.refresh;

  const pdfInputRef = useRef<HTMLInputElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const researchAbortRef = useRef<AbortController | null>(null);
  const streamAbortRef = useRef<AbortController | null>(null);
  const researchTaskIdRef = useRef<string | null>(null);
  const userCancelledRef = useRef(false);

  useEffect(() => {
    if (live.documents.length > 0) {
      setDocuments((prev) => {
        const seen = new Set(prev.map((d) => d.document_id));
        const merged = [...prev];
        for (const doc of live.documents) {
          if (!seen.has(doc.id)) {
            merged.push({
              document_id: doc.id,
              filename: doc.name,
              size: doc.size_bytes ?? 0,
              status: doc.status,
              page_count: doc.pages ?? 0,
            });
            seen.add(doc.id);
          }
        }
        return merged;
      });
    }
  }, [live.documents]);

  useEffect(() => {
    listDocuments()
      .then((existingDocuments) => {
        setDocuments(mapUploadedDocuments(existingDocuments));
      })
      .catch((error) => log.warn("Failed to load documents", { error }));
  }, []);

  useEffect(() => {
    if (!token || !workspaceId) return;
    const callbacks = {
      onResearchStart: (payload: { userId: string; userName: string; taskId: string; query: string }) => {
        if (payload.userId !== currentUserId) {
          setLogs((prev) => [...prev, {
            agent: "collaboration",
            action: "research_started",
            status: "running",
            timestamp: Date.now() / 1000,
            details: `${payload.userName} started research: "${payload.query}"`,
          }]);
        }
      },
      onResearchComplete: (payload: { taskId: string; userId: string }) => {
        if (payload.userId !== currentUserId) {
          setLogs((prev) => [...prev, {
            agent: "collaboration",
            action: "research_completed",
            status: "completed",
            timestamp: Date.now() / 1000,
            details: `Research completed by another user`,
          }]);
        }
      },
    };
    collaborationClient.connect(workspaceId, token, callbacks);
    return () => collaborationClient.disconnect(callbacks);
  }, [token, workspaceId, currentUserId]);

  const handleSend = useCallback(
    async (query: string, opts?: { replaceLastUserMessage?: boolean }) => {
      const now = Date.now();
      const userMessage: Message = {
        id: `${now}-user`,
        role: "user",
        content: query,
        timestamp: now,
      };
      const thinkingMessage: Message = {
        id: `${now}-thinking`,
        role: "assistant",
        content: "Thinking...",
        timestamp: now,
      };

      setRunError(null);
      userCancelledRef.current = false;
      setMessages((current) => {
        // Retry re-uses the last user message: drop that message and anything
        // after it (the failed/cancelled bubble) so it does not duplicate.
        if (opts?.replaceLastUserMessage) {
          const lastUserIdx = current.map((m) => m.role).lastIndexOf("user");
          if (lastUserIdx >= 0) current = current.slice(0, lastUserIdx);
        }
        return [...current, userMessage, thinkingMessage];
      });
      setIsRunning(true);
      setLogs([]);
      setPlan([]);
      setSources([]);
      setAgentMetrics({});
      setExecutionTime(undefined);

      const taskId = crypto.randomUUID();
      researchTaskIdRef.current = taskId;
      const streamController = subscribeResearchLogs(taskId, {
        onLog: (entry) => {
          if (entry.agent === "system" && entry.action === "session" && entry.details) {
            setSupabaseSessionId(entry.details);
            refreshLiveWorkspace();
          }
          setLogs((prev) => {
            const idx = prev.findIndex(
              (e) => e.agent === entry.agent && e.action === entry.action
            );
            if (idx >= 0) {
              const next = [...prev];
              next[idx] = entry;
              return next;
            }
            return [...prev, entry];
          });
        },
      });
      streamAbortRef.current = streamController;
      const abortController = new AbortController();
      researchAbortRef.current = abortController;

      try {
        const result = await runResearch(
          query,
          selectedDocs,
          providerSettings,
          taskId,
          conversationId || undefined,
          debateMode,
          abortController.signal,
        );

        setPlan(result.plan || []);
        setLogs(result.logs || []);
        setSources(result.sources || []);
        setAgentMetrics(result.agent_metrics || {});
        setExecutionTime(result.execution_time);
        if (result.conversation_id) setConversationId(result.conversation_id);
        setConversationsRefreshKey((k) => k + 1);

        if (!result.answer?.trim()) {
          throw new Error(
            result.errors?.join("; ") ||
              "No answer was generated. Check Settings → OpenRouter is selected and the backend is running."
          );
        }

        setMessages((current) => [
          ...current.filter((message) => message.id !== thinkingMessage.id),
          {
            id: `${Date.now()}-assistant`,
            role: "assistant",
            content: result.answer || "",
            timestamp: Date.now(),
            sources: result.sources,
            logs: result.logs,
            status: result.status,
            debate: result.debate,
            answerMode: result.answer_mode,
            evidenceSummary: result.evidence_summary,
            hasEvidence: result.has_evidence,
          },
        ]);
      } catch (error) {
        if (
          userCancelledRef.current ||
          (error instanceof ApiClientError && error.code === "ABORTED")
        ) {
          setMessages((current) => [
            ...current.filter((message) => message.id !== thinkingMessage.id),
            {
              id: `${Date.now()}-cancelled`,
              role: "assistant",
              content: "**Research cancelled.** The workspace is idle and ready for a new query.",
              timestamp: Date.now(),
            },
          ]);
        } else {
          log.error("Research run failed", { error, taskId });
          const copy = errorCopy(error);
          setMessages((current) => [
            ...current.filter((message) => message.id !== thinkingMessage.id),
            {
              id: `${Date.now()}-error`,
              role: "assistant",
              content: copy.message,
              timestamp: Date.now(),
            },
          ]);
          setRunError(copy.runError);
        }
      } finally {
        streamController.abort();
        streamAbortRef.current = null;
        researchAbortRef.current = null;
        researchTaskIdRef.current = null;
        setIsRunning(false);
        refreshLiveWorkspace();
      }
    },
    [selectedDocs, providerSettings, debateMode, conversationId, refreshLiveWorkspace],
  );

  const handleRetryResearch = useCallback(() => {
    const lastQuery = [...messages].reverse().find((m) => m.role === "user")?.content;
    if (!lastQuery || isRunning) return;
    void handleSend(lastQuery, { replaceLastUserMessage: true });
  }, [messages, handleSend, isRunning]);

  const handleNewChat = useCallback(() => {
    setMessages([]);
    setLogs([]);
    setPlan([]);
    setSources([]);
    setAgentMetrics({});
    setExecutionTime(undefined);
    setRunError(null);
    userCancelledRef.current = false;
    setConversationId(null);
    setSidebarOpen(false);
  }, []);

  const handleClearAll = useCallback(() => {
    setMessages([]);
    setLogs([]);
    setPlan([]);
    setSources([]);
    setDocuments([]);
    setSelectedDocs([]);
    setAgentMetrics({});
    setExecutionTime(undefined);
    setRunError(null);
    userCancelledRef.current = false;
    setConversationId(null);
  }, []);

  const handleSelectConversation = useCallback(async (id: string) => {
    try {
      // loadConversation returns ConversationDetail directly (not wrapped)
      const data = await loadConversation(id);
      setConversationId(id);
      const msgs = Array.isArray(data.messages) ? data.messages : [];
      setMessages(mapConversationMessages(msgs));
    } catch (error) {
      log.warn("Failed to load conversation", { conversationId: id, error });
    }
  }, []);

  const handleCancelResearch = useCallback(() => {
    userCancelledRef.current = true;
    const taskId = researchTaskIdRef.current;
    researchAbortRef.current?.abort();
    streamAbortRef.current?.abort();
    // Server-side cancel: terminates the background graph task so provider
    // work stops and the run is persisted with a terminal "cancelled" state.
    if (taskId) {
      cancelResearch(taskId).catch((error) => {
        /* local aborts already stop the client; server cleanup is best-effort */
        log.warn("Failed to cancel research on server", { taskId, error });
      });
    }
  }, []);

  const handleDocumentUpload = useCallback((files: FileList | null) => {
    if (!files) return;
    for (const file of Array.from(files)) {
      uploadPDF(file)
        .then((doc) => {
          setDocuments((prev) => [...prev, doc]);
        })
        .catch((error) => log.error("Failed to upload document", { filename: file.name, error }));
    }
  }, []);

  const openDocumentPicker = useCallback(() => {
    pdfInputRef.current?.click();
    setSidebarOpen(false);
  }, []);

  const focusComposer = useCallback(() => {
    composerRef.current?.focus();
    setPaletteOpen(false);
  }, []);

  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent) => {
      if (!event.metaKey && !event.ctrlKey) return;
      const key = event.key.toLowerCase();
      if (key === "k") {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      } else if (key === "n") {
        event.preventDefault();
        setPaletteOpen(false);
        handleNewChat();
      } else if (key === "u") {
        event.preventDefault();
        openDocumentPicker();
      } else if (key === ",") {
        event.preventDefault();
        setPaletteOpen(false);
        setSettingsOpen(true);
      }
    };

    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, [handleNewChat, openDocumentPicker]);

  const recentQueries = useMemo(
    () =>
      messages
        .filter((message) => message.role === "user")
        .map((message) => message.content)
        .slice(-5)
        .reverse(),
    [messages],
  );

  const query = useMemo(
    () => messages.find((m) => m.role === "user")?.content || "",
    [messages],
  );

  const lastAnswer = useMemo(
    () => [...messages].reverse().find((m) => m.role === "assistant" && m.content !== "Thinking..." && m.content !== "...")?.content || "",
    [messages],
  );

  // Phase 5: merge Supabase Realtime state with the SSE/response state so
  // panels stay live even after the response resolves.
  const mergedAgentMetrics = useMemo(
    () => ({ ...realtime.agentMetrics, ...agentMetrics }),
    [realtime.agentMetrics, agentMetrics],
  );
  const mergedExecutionTime = useMemo(
    () =>
      executionTime ??
      (realtime.executionTimeMs != null ? realtime.executionTimeMs / 1000 : undefined),
    [executionTime, realtime.executionTimeMs],
  );
  const mergedLogs = useMemo(
    () => mergeAgentLogs(logs, realtime.agentLogs),
    [logs, realtime.agentLogs],
  );
  const mergedDocuments = useMemo<UploadedDocument[]>(
    () => mergeDocuments(documents, realtime.documents),
    [documents, realtime.documents],
  );
  const mergedSourceCount = sources.length || realtime.sourcesFound;

  const phase = researchPhase(isRunning, runError, messages.length);

  return {
    // conversation state
    messages,
    isRunning,
    logs,
    plan,
    sources,
    runError,
    phase,
    conversationId,
    recentQueries,
    query,
    lastAnswer,
    // documents
    documents,
    mergedDocuments,
    selectedDocs,
    setSelectedDocs,
    setDocuments,
    pdfInputRef,
    handleDocumentUpload,
    // metrics
    mergedAgentMetrics,
    mergedExecutionTime,
    mergedLogs,
    mergedSourceCount,
    // workspace data
    live,
    // settings
    providerSettings,
    setProviderSettings,
    debateMode,
    setDebateMode,
    // panels
    sidebarOpen,
    setSidebarOpen,
    workflowOpen,
    setWorkflowOpen,
    paletteOpen,
    setPaletteOpen,
    settingsOpen,
    setSettingsOpen,
    chatOpen,
    setChatOpen,
    inspectedSource,
    setInspectedSource,
    conversationsRefreshKey,
    // actions
    composerRef,
    handleSend,
    handleRetryResearch,
    handleNewChat,
    handleClearAll,
    handleSelectConversation,
    handleCancelResearch,
    openDocumentPicker,
    focusComposer,
  };
}

export type ResearchWorkspaceController = ReturnType<typeof useResearchWorkspace>;
