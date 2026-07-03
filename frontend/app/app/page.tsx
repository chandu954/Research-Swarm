"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  PanelLeft,
  Scale,
  Sparkles,
} from "lucide-react";

import AgentLogs from "@/components/AgentLogs";
import Chat from "@/components/Chat";
import CommandPalette from "@/components/CommandPalette";
import ExecutionTimeline from "@/components/ExecutionTimeline";
import MetricsPanel from "@/components/MetricsPanel";
import PDFUploader from "@/components/PDFUploader";
import SettingsPanel from "@/components/Settings";
import Sidebar from "@/components/Sidebar";
import Sources from "@/components/Sources";
import Topbar from "@/components/Topbar";
import KnowledgeGraph from "@/components/KnowledgeGraph";
import ReportGenerator from "@/components/ReportGenerator";
import AnalyticsDashboard from "@/components/AnalyticsDashboard";
import SourceInspector from "@/components/SourceInspector";
import { listDocuments, runResearch, subscribeResearchLogs, uploadPDF, loadConversation, ApiClientError } from "@/lib/api";
import { useProviderSettings } from "@/lib/useSettings";
import type {
  AgentMetric,
  AgentLog,
  ExecutionStep,
  Message,
  SourceCitation,
  UploadedDocument,
} from "@/lib/types";

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
  const [elapsed, setElapsed] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [workflowOpen, setWorkflowOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [inspectedSource, setInspectedSource] = useState<SourceCitation | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [debateMode, setDebateMode] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const { settings: providerSettings, update: setProviderSettings } = useProviderSettings();

  useEffect(() => {
    listDocuments()
      .then((existingDocuments) => {
        setDocuments(existingDocuments || []);
      })
      .catch((err) => console.warn("Failed to load documents:", err));
  }, []);

  useEffect(() => {
    if (!isRunning) {
      setElapsed(0);
      return;
    }
    const start = Date.now();
    const interval = setInterval(() => {
      setElapsed((Date.now() - start) / 1000);
    }, 250);
    return () => clearInterval(interval);
  }, [isRunning]);

  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
    };

    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, []);

  const handleSend = useCallback(
    async (query: string) => {
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

      setMessages((current) => [...current, userMessage, thinkingMessage]);
      setIsRunning(true);
      setLogs([]);
      setPlan([]);
      setSources([]);
      setAgentMetrics({});
      setExecutionTime(undefined);

      const taskId = crypto.randomUUID();
      const streamController = subscribeResearchLogs(taskId, {
        onLog: (log) => {
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

      try {
        const result = await runResearch(
          query,
          selectedDocs,
          providerSettings,
          taskId,
          conversationId || undefined,
          debateMode,
        );

        setPlan(result.plan || []);
        setLogs(result.logs || []);
        setSources(result.sources || []);
        setAgentMetrics(result.agent_metrics || {});
        setExecutionTime(result.execution_time);
        if (result.conversation_id) setConversationId(result.conversation_id);

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
      } finally {
        streamController.abort();
        setIsRunning(false);
      }
    },
    [selectedDocs, providerSettings, debateMode, conversationId],
  );

  const handleNewChat = useCallback(() => {
    setMessages([]);
    setLogs([]);
    setPlan([]);
    setSources([]);
    setAgentMetrics({});
    setExecutionTime(undefined);
    setElapsed(0);
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
    setElapsed(0);
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

  const openDocumentPicker = useCallback(() => {
    pdfInputRef.current?.click();
    setSidebarOpen(false);
  }, []);

  const focusComposer = useCallback(() => {
    composerRef.current?.focus();
    setPaletteOpen(false);
  }, []);

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
        className={`fixed inset-y-0 left-0 z-40 w-[264px] border-r transition-transform duration-220 ease-out lg:static lg:block ${
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
          onClearAll={handleClearAll}
          onNewChat={handleNewChat}
          onOpenDocuments={openDocumentPicker}
          onOpenSettings={() => setSettingsOpen(true)}
          onSelectConversation={handleSelectConversation}
          activeConversationId={conversationId}
        />
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <Topbar
          onToggleSidebar={() => setSidebarOpen(true)}
          onOpenSettings={() => setSettingsOpen(true)}
          onOpenPalette={() => setPaletteOpen(true)}
          provider={providerSettings.provider}
        />

        <div className="relative flex min-h-0 flex-1">
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
              isRunning={isRunning}
              streamLogs={logs}
              elapsed={elapsed}
              composerRef={composerRef}
              debateMode={debateMode}
              onDebateToggle={() => setDebateMode((prev) => !prev)}
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
              <ReportGenerator query={query} messages={messages} sources={sources} />
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
            <div className="space-y-6 p-4">
              <ExecutionTimeline
                logs={logs}
                agentMetrics={agentMetrics}
                isRunning={isRunning}
              />
              <MetricsPanel
                agentMetrics={agentMetrics}
                executionTime={executionTime}
                sourceCount={sources.length}
                documentCount={selectedDocs.length}
              />
              <AnalyticsDashboard
                agentMetrics={agentMetrics}
                logs={logs}
                executionTime={executionTime}
                sourceCount={sources.length}
                isRunning={isRunning}
              />
              <PDFUploader
                documents={documents}
                onDocumentsChange={setDocuments}
                selectedDocs={selectedDocs}
                onSelectionChange={setSelectedDocs}
              />
              <AgentLogs logs={logs} plan={plan} isRunning={isRunning} />
              <Sources sources={sources} onInspect={setInspectedSource} />
              {lastAnswer && (
                <KnowledgeGraph answer={lastAnswer} sources={sources} />
              )}
            </div>
          </aside>
        </div>
      </section>

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
