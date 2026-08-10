"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  PanelLeft,
  Scale,
  Sparkles,
  MessageSquare,
} from "lucide-react";

import AgentLogs from "@/components/AgentLogs";
import Chat from "@/components/Chat";
import { ChatSidebar } from "@/components/ChatSidebar";
import CommandPalette from "@/components/CommandPalette";
import ExecutionTimeline from "@/components/ExecutionTimeline";
import MetricsPanel from "@/components/MetricsPanel";
import PDFUploader from "@/components/PDFUploader";
import SettingsPanel from "@/components/Settings";
import Sidebar from "@/components/Sidebar";
import Sources from "@/components/Sources";
import Topbar from "@/components/Topbar";
import dynamic from "next/dynamic";
import { KnowledgeGraphSkeleton } from "@/components/Skeletons";

const KnowledgeGraph = dynamic(() => import("@/components/KnowledgeGraph"), {
  ssr: false,
  loading: () => <KnowledgeGraphSkeleton />,
});
import ReportGenerator from "@/components/ReportGenerator";
import ReportsPanel from "@/components/ReportsPanel";
import SourceInspector from "@/components/SourceInspector";
import WorkflowOverview from "@/components/WorkflowOverview";
import { listDocuments, runResearch, cancelResearch, subscribeResearchLogs, uploadPDF, loadConversation, ApiClientError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useProviderSettings } from "@/lib/useSettings";
import { collaborationClient } from "@/lib/websocket";
import { useTenant } from "@/lib/tenant";
import { useRealtimeWorkspace } from "@/lib/supabase/realtime";
import { useLiveWorkspace } from "@/lib/supabase/query";
import { useElapsed } from "@/lib/useElapsed";
import type {
  AgentMetric,
  AgentLog,
  ExecutionStep,
  Message,
  SourceCitation,
  UploadedDocument,
} from "@/lib/types";

// Self-contained elapsed timer for the workflow header. Owns its own 250ms
// tick so the rest of the workspace tree is never re-rendered while running.
function ResearchProgressTimer() {
  const elapsed = useElapsed(true);
  return (
    <div className="mt-2.5 flex items-center justify-between text-[10px] text-[var(--text-muted)]">
      <span>Research in progress</span>
      <span className="font-mono">{Math.floor(elapsed)}s</span>
    </div>
  );
}

interface ConversationMessageResponse {
  id?: string;
  message_id?: string;
  role: string;
  content?: string;
  created_at?: number;
  timestamp?: number;
  sources?: SourceCitation[];
}

export default function ResearchWorkspace() {
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
  const realtime = useRealtimeWorkspace(supabaseSessionId);
  const live = useLiveWorkspace();

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
        const mapped = (Array.isArray(existingDocuments) ? existingDocuments : []).map(
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
        setDocuments(mapped);
      })
      .catch((err) => console.warn("Failed to load documents:", err));
  }, []);

  useEffect(() => {
    if (!token || !currentWorkspace) return;
    const callbacks = {
      onResearchStart: (payload: { userId: string; userName: string; taskId: string; query: string }) => {
        if (payload.userId !== user?.id) {
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
        if (payload.userId !== user?.id) {
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
    collaborationClient.connect(currentWorkspace.id, token, callbacks);
    return () => collaborationClient.disconnect(callbacks);
  }, [token, currentWorkspace?.id]);

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
        onLog: (log) => {
          if (log.agent === "system" && log.action === "session" && log.details) {
            setSupabaseSessionId(log.details);
            live.refresh();
          }
          setLogs((prev) => {
            const idx = prev.findIndex(
              (e) => e.agent === log.agent && e.action === log.action
            );
            if (idx >= 0) {
              const next = [...prev];
              next[idx] = log;
              return next;
            }
            return [...prev, log];
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
          const msg = error instanceof ApiClientError
            ? `**${error.message}**\n\n> ${error.code === "OFFLINE" ? "The backend may be offline. Check your connection." : error.code === "TIMEOUT" ? "The research took too long. Try a simpler query." : error.code === "UNAUTHORIZED" ? "Your session expired. Please sign in again." : ""}`
            : error instanceof Error
              ? `**Error**: ${error.message}`
              : "**Error**: An unexpected error occurred. Please try again.";
          setMessages((current) => [
            ...current.filter((message) => message.id !== thinkingMessage.id),
            {
              id: `${Date.now()}-error`,
              role: "assistant",
              content: msg,
              timestamp: Date.now(),
            },
          ]);
          setRunError(
            error instanceof ApiClientError
              ? error.code === "OFFLINE"
                ? "The backend may be offline. Check your connection and try again."
                : error.code === "TIMEOUT"
                  ? "The research took too long. Try again or use a simpler query."
                  : error.code === "UNAUTHORIZED"
                    ? "Your session expired. Please sign in again."
                    : error.message
              : error instanceof Error
                ? error.message
                : "An unexpected error occurred. Please try again.",
          );
        }
      } finally {
        streamController.abort();
        streamAbortRef.current = null;
        researchAbortRef.current = null;
        researchTaskIdRef.current = null;
        setIsRunning(false);
        live.refresh();
      }
    },
    [selectedDocs, providerSettings, debateMode, conversationId, live.refresh],
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
      setMessages(msgs.map((m: ConversationMessageResponse) => ({
        id: m.id || m.message_id || crypto.randomUUID(),
        role: m.role as Message["role"],
        content: m.content || "",
        timestamp: m.created_at || m.timestamp || Date.now(),
        sources: m.sources || [],
      })));
    } catch (err) {
      console.warn("Failed to load conversation:", err);
    }
  }, []);

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

  const pdfInputRef = useRef<HTMLInputElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const researchAbortRef = useRef<AbortController | null>(null);
  const streamAbortRef = useRef<AbortController | null>(null);
  const researchTaskIdRef = useRef<string | null>(null);
  const userCancelledRef = useRef(false);

  const handleCancelResearch = useCallback(() => {
    userCancelledRef.current = true;
    const taskId = researchTaskIdRef.current;
    researchAbortRef.current?.abort();
    streamAbortRef.current?.abort();
    // Server-side cancel: terminates the background graph task so provider
    // work stops and the run is persisted with a terminal "cancelled" state.
    if (taskId) {
      cancelResearch(taskId).catch(() => {
        /* local aborts already stop the client; server cleanup is best-effort */
      });
    }
  }, []);

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
  const mergedLogs = useMemo(() => {
    const next = [...logs];
    for (const rtLog of realtime.agentLogs) {
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
  }, [logs, realtime.agentLogs]);
  const mergedDocuments = useMemo<UploadedDocument[]>(() => {
    const next = [...documents];
    for (const rtDoc of realtime.documents) {
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
  }, [documents, realtime.documents]);
  const mergedSourceCount = sources.length || realtime.sourcesFound;

  const phase: "idle" | "running" | "completed" | "failed" = isRunning
    ? "running"
    : runError
      ? "failed"
      : messages.length === 0
        ? "idle"
        : "completed";

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

  return (
    <main className="workspace-shell flex h-screen overflow-hidden">
      {sidebarOpen && (
        <button
          className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm lg:hidden"
          aria-label="Close navigation"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 w-[240px] border-r transition-transform duration-220 ease-out lg:static lg:block ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        }`}
        style={{
          borderColor: "var(--border)",
          backgroundColor: "var(--surface)",
        }}
      >
        <Sidebar
          documents={documents}
          recentQueries={recentQueries}
          collections={live.collections.map((c) => c.name)}
          conversations={live.sessions.map((s) => ({
            id: s.id,
            query: s.title || s.prompt,
            timestamp: s.updated_at || s.created_at,
            turn_count: 0,
          }))}
          onClearAll={handleClearAll}
          onNewChat={handleNewChat}
          onOpenDocuments={openDocumentPicker}
          onOpenSettings={() => setSettingsOpen(true)}
          onSelectConversation={handleSelectConversation}
          activeConversationId={conversationId}
          refreshKey={conversationsRefreshKey}
        />
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <Topbar
          onToggleSidebar={() => setSidebarOpen(true)}
          onOpenSettings={() => setSettingsOpen(true)}
          onOpenPalette={() => setPaletteOpen(true)}
        />

        <div className="relative flex min-h-0 flex-1">
          <button
            onClick={() => setChatOpen((open) => !open)}
            className="fixed bottom-4 right-16 z-30 flex h-10 w-10 items-center justify-center rounded-xl border border-white/[0.08] bg-[var(--surface)] shadow-lg backdrop-blur-xl"
            aria-label="Toggle chat"
          >
            <MessageSquare className="h-4 w-4 text-[var(--text-secondary)]" />
          </button>
          <button
            onClick={() => setWorkflowOpen((open) => !open)}
            className="fixed bottom-4 right-4 z-30 flex h-10 w-10 items-center justify-center rounded-xl border border-white/[0.08] bg-[var(--surface)] shadow-lg backdrop-blur-xl xl:hidden"
            aria-label="Toggle workflow panel"
          >
            <PanelLeft className="h-4 w-4 rotate-180 text-[var(--text-secondary)]" />
          </button>
          <section className="min-w-0 flex-1">
            <Chat
              messages={messages}
              documents={documents}
              onSend={handleSend}
              onAttach={openDocumentPicker}
              onCancel={handleCancelResearch}
              isRunning={isRunning}
              streamLogs={logs}
              composerRef={composerRef}
              debateMode={debateMode}
              onDebateToggle={() => setDebateMode((prev) => !prev)}
              liveSessions={live.sessions}
              liveLastSession={live.sessions[0] ?? null}
              collections={live.collections}
              reports={live.reports}
              runError={runError}
              onRetry={handleRetryResearch}
            />
            <input
              ref={pdfInputRef}
              type="file"
              accept=".pdf"
              multiple
              className="sr-only"
              onChange={(e) => {
                const files = e.target.files;
                if (files) {
                  for (const file of Array.from(files)) {
                    uploadPDF(file).then((doc) => {
                      setDocuments((prev) => [...prev, doc]);
                    }).catch(console.error);
                  }
                }
                e.target.value = "";
              }}
            />
            <div className="mx-auto w-full max-w-4xl px-5 pb-2 sm:px-8">
              {messages.length > 0 && (
                <ReportGenerator query={query} messages={messages} sources={sources} />
              )}
            </div>
          </section>

          {workflowOpen && (
            <button
              className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm xl:hidden"
              aria-label="Close workflow panel"
              onClick={() => setWorkflowOpen(false)}
            />
          )}

          <aside
            className={`workflow-panel fixed inset-y-0 right-0 z-40 w-[350px] translate-x-full overflow-y-auto xl:static xl:z-auto xl:block xl:translate-x-0 ${
              workflowOpen ? "!translate-x-0" : ""
            }`}
          >
            <div className="sticky top-0 z-10 border-b border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_88%,transparent)] px-4 py-3 backdrop-blur-lg">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-semibold tracking-tight text-[var(--text-primary)]">
                  Workflow
                </p>
                <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--surface-hover)] px-2.5 py-1 text-[9px] font-medium uppercase tracking-[0.08em] text-[var(--text-secondary)]">
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${
                      phase === "running"
                        ? "animate-pulse bg-violet-400"
                        : phase === "failed"
                          ? "bg-rose-400"
                          : phase === "completed"
                            ? "bg-emerald-400"
                            : "bg-[var(--text-muted)]"
                    }`}
                  />
                  {phase}
                </span>
              </div>
              {phase === "running" && <ResearchProgressTimer />}
            </div>

            <div className="space-y-5 p-4">
              {phase === "idle" && (
                <div className="unified-panel">
                  <WorkflowOverview bare lastSession={live.sessions[0] ?? null} />
                  <ReportsPanel
                    reports={live.reports}
                    onStartResearch={focusComposer}
                    bare
                  />
                  <PDFUploader
                    documents={mergedDocuments}
                    onDocumentsChange={setDocuments}
                    selectedDocs={selectedDocs}
                    onSelectionChange={setSelectedDocs}
                  />
                </div>
              )}

              {phase === "running" && (
                <div className="unified-panel">
                  <ExecutionTimeline
                    logs={mergedLogs}
                    agentMetrics={mergedAgentMetrics}
                    isRunning={isRunning}
                  />
                  <MetricsPanel
                    agentMetrics={mergedAgentMetrics}
                    executionTime={mergedExecutionTime}
                    sourceCount={mergedSourceCount}
                    documentCount={selectedDocs.length}
                    lastRun={live.lastMetrics}
                  />
                  <Sources sources={sources} onInspect={setInspectedSource} />
                  <AgentLogs logs={mergedLogs} plan={plan} isRunning={isRunning} />
                </div>
              )}

              {phase === "completed" && (
                <>
                  <div className="unified-panel">
                    <MetricsPanel
                      agentMetrics={mergedAgentMetrics}
                      executionTime={mergedExecutionTime}
                      sourceCount={mergedSourceCount}
                      documentCount={selectedDocs.length}
                      lastRun={live.lastMetrics}
                    />
                    <Sources sources={sources} onInspect={setInspectedSource} />
                    <ReportsPanel
                      reports={live.reports}
                      onStartResearch={focusComposer}
                      bare
                    />
                  </div>
                  {lastAnswer && (
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.3 }}
                    >
                      <KnowledgeGraph answer={lastAnswer} sources={sources} />
                    </motion.div>
                  )}
                </>
              )}
            </div>
          </aside>
        </div>
      </section>

      <ChatSidebar open={chatOpen} onClose={() => setChatOpen(false)} />

      <SettingsPanel
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        settings={providerSettings}
        onSettingsChange={(s) => setProviderSettings(s)}
      />

      <SourceInspector source={inspectedSource} onClose={() => setInspectedSource(null)} />

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onNewChat={handleNewChat}
        onFocusComposer={focusComposer}
        onOpenDocuments={openDocumentPicker}
      />
    </main>
  );
}
