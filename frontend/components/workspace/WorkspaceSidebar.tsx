"use client";

import Sidebar from "@/components/Sidebar";
import type { ResearchWorkspaceController } from "@/lib/useResearchWorkspace";

export default function WorkspaceSidebar({
  workspace,
}: {
  workspace: ResearchWorkspaceController;
}) {
  const {
    documents,
    recentQueries,
    live,
    handleClearAll,
    handleNewChat,
    openDocumentPicker,
    setSettingsOpen,
    handleSelectConversation,
    conversationId,
    conversationsRefreshKey,
  } = workspace;

  return (
    <aside
      className={`fixed inset-y-0 left-0 z-40 w-[240px] border-r transition-transform duration-220 ease-out lg:static lg:block ${
        workspace.sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
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
  );
}
