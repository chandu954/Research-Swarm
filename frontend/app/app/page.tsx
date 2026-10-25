"use client";

import { MessageSquare, PanelLeft } from "lucide-react";

import Chat from "@/components/Chat";
import { ChatSidebar } from "@/components/ChatSidebar";
import CommandPalette from "@/components/CommandPalette";
import ReportGenerator from "@/components/ReportGenerator";
import SettingsPanel from "@/components/Settings";
import SourceInspector from "@/components/SourceInspector";
import Topbar from "@/components/Topbar";
import WorkspaceSidebar from "@/components/workspace/WorkspaceSidebar";
import WorkflowPanel from "@/components/workspace/WorkflowPanel";
import { useResearchWorkspace } from "@/lib/useResearchWorkspace";

export default function ResearchWorkspace() {
  const workspace = useResearchWorkspace();
  const {
    messages,
    documents,
    logs,
    sources,
    query,
    isRunning,
    debateMode,
    runError,
    providerSettings,
    pdfInputRef,
    composerRef,
    sidebarOpen,
    workflowOpen,
    paletteOpen,
    settingsOpen,
    chatOpen,
    inspectedSource,
    handleSend,
    handleCancelResearch,
    handleRetryResearch,
    handleNewChat,
    handleDocumentUpload,
    openDocumentPicker,
    focusComposer,
    setDebateMode,
    setSidebarOpen,
    setWorkflowOpen,
    setPaletteOpen,
    setSettingsOpen,
    setChatOpen,
    setInspectedSource,
    setProviderSettings,
    live,
  } = workspace;

  return (
    <main className="workspace-shell flex h-screen overflow-hidden">
      {sidebarOpen && (
        <button
          className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm lg:hidden"
          aria-label="Close navigation"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <WorkspaceSidebar workspace={workspace} />

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
                handleDocumentUpload(e.target.files);
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

          <WorkflowPanel workspace={workspace} />
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
