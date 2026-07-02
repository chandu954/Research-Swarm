"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ChevronDown,
  Command,
  Menu,
  Network,
  PanelLeft,
  Sparkles,
  Wifi,
} from "lucide-react";
import { motion } from "framer-motion";
import AgentLogs from "@/components/AgentLogs";
import Chat from "@/components/Chat";
import CommandPalette from "@/components/CommandPalette";
import ExecutionTimeline from "@/components/ExecutionTimeline";
import MetricsPanel from "@/components/MetricsPanel";
import PDFUploader from "@/components/PDFUploader";
import ProviderHealth from "@/components/ProviderHealth";
import SettingsPanel from "@/components/Settings";
import Sidebar from "@/components/Sidebar";
import Sources from "@/components/Sources";
import { listDocuments, runResearch, subscribeResearchLogs } from "@/lib/api";
import { useProviderSettings } from "@/lib/useSettings";
import type {
  AgentMetric,
  AgentLog,
  ExecutionStep,
  Message,
  SourceCitation,
  UploadedDocument,
} from "@/lib/types";

export default function ResearchWorkspace() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [logs, setLogs] = useState<AgentLog[]>([]);
  const [plan, setPlan] = useState<ExecutionStep[]>([]);
  const [sources, setSources] = useState<SourceCitation[]>([]);
  const [agentMetrics, setAgentMetrics] = useState<
    Record<string, AgentMetric>
  >({});
  const [executionTime, setExecutionTime] = useState<number>();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [workflowOpen, setWorkflowOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const { settings: providerSettings, update: setProviderSettings } = useProviderSettings();

  useEffect(() => {
    listDocuments()
      .then(({ documents: existingDocuments }) => {
        setDocuments(existingDocuments);
      })
      .catch(() => {
        // The workspace remains usable if the document list is unavailable.
      });
  }, []);

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
          taskId
        );

        setPlan(result.plan || []);
        setLogs(result.logs || []);
        setSources(result.sources || []);
        setAgentMetrics(result.agent_metrics || {});
        setExecutionTime(result.execution_time);

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
          },
        ]);
      } catch (error) {
        setMessages((current) => [
          ...current.filter((message) => message.id !== thinkingMessage.id),
          {
            id: `${Date.now()}-error`,
            role: "assistant",
            content: `**Error**: ${
              error instanceof Error
                ? error.message
                : "An unexpected error occurred. Please try again."
            }`,
            timestamp: Date.now(),
          },
        ]);
      } finally {
        streamController.abort();
        setIsRunning(false);
      }
    },
    [selectedDocs, providerSettings],
  );

  const handleNewChat = useCallback(() => {
    setMessages([]);
    setLogs([]);
    setPlan([]);
    setSources([]);
    setAgentMetrics({});
    setExecutionTime(undefined);
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

  const openDocumentPicker = useCallback(() => {
    document.getElementById("pdf-upload")?.click();
    setSidebarOpen(false);
  }, []);

  const focusComposer = useCallback(() => {
    document.getElementById("research-composer")?.focus();
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

      <motion.aside
        initial={false}
        animate={{ x: sidebarOpen ? 0 : undefined }}
        className={`fixed inset-y-0 left-0 z-40 w-[264px] border-r lg:static lg:block ${
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
        />
      </motion.aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="workspace-header">
          <div className="flex min-w-0 items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="icon-button lg:hidden"
              aria-label="Open navigation"
            >
              <Menu className="h-4 w-4" />
            </button>
            <Link href="/" className="brand-mark h-8 w-8 lg:hidden">
              <Sparkles className="h-4 w-4" />
            </Link>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="truncate text-sm font-semibold text-[var(--text-primary)]">
                  Research workspace
                </h1>
                <span className="hidden rounded-md border border-violet-400/20 bg-violet-500/10 px-1.5 py-0.5 text-[9px] font-semibold text-violet-300 sm:inline">
                  BETA
                </span>
              </div>
              <p className="hidden text-[10px] text-[var(--text-muted)] sm:block">
                Multi-agent research platform
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="hidden items-center gap-2 xl:flex">
              <span className="tech-badge">
                <Network className="h-3 w-3 text-violet-400" />
                LangGraph
              </span>
              <ProviderHealth
                provider={providerSettings.provider}
                openrouterKey={providerSettings.openrouterKey}
              />
            </div>
            <button
              onClick={() => setPaletteOpen(true)}
              className="command-trigger"
              aria-label="Open command palette"
            >
              <Command className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Search</span>
              <kbd>⌘K</kbd>
            </button>
            <button className="profile-button" aria-label="Open profile menu">
              <span>AS</span>
              <ChevronDown className="hidden h-3 w-3 text-[var(--text-muted)] sm:block" />
            </button>
            <button
              onClick={() => setWorkflowOpen((open) => !open)}
              className="icon-button xl:hidden"
              aria-label="Toggle AI workflow"
            >
              <PanelLeft className="h-4 w-4 rotate-180" />
            </button>
          </div>
        </header>

        <div className="relative flex min-h-0 flex-1">
          <section className="min-w-0 flex-1">
            <Chat
              messages={messages}
              documents={documents}
              onSend={handleSend}
              onAttach={openDocumentPicker}
              isRunning={isRunning}
              streamLogs={logs}
            />
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
              <PDFUploader
                documents={documents}
                onDocumentsChange={setDocuments}
                selectedDocs={selectedDocs}
                onSelectionChange={setSelectedDocs}
              />
              <AgentLogs logs={logs} plan={plan} isRunning={isRunning} />
              <Sources sources={sources} />
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
